#!/usr/bin/env python
"""U6.7：在 validation 上重算 collie-pair 的完整概率与组内份额（只读）。

为什么必须重算
--------------
U6.6 留存的逐图记录只保存了首选概率与前 5 名，无法计算
``share = min(p_collie, p_border_collie) / pair_mass``。本脚本用 exp06 权重
按 **256** 分辨率完整前向一次，导出两类概率与组内份额，再按预设网格
比较"原策略（绝对分差）"与"新策略（组内相对份额）"。

边界
----
* 只读 ``data/v2_processed/val``；脚本内断言路径不含 test。
* 不训练、不写正式 DB/uploads、不修改任何权重。
* 阈值选择规则在看数据之前已写定（见 plan / README 与最终报告）。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from torchvision import datasets

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ml.dataset import build_transforms  # noqa: E402
from ml.model import load_checkpoint, resolve_device  # noqa: E402

COLLIE = "collie"
BORDER = "border_collie"

MASS_THRESHOLD = 0.30            # 两类组组内总质量门槛（不变）
LEGACY_MARGIN_THRESHOLD = 0.30   # v1 的绝对分差阈值（用于对照）
SHARE_GRID = (0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--class-names", type=Path, required=True)
    parser.add_argument("--split", default="val")
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    split_dir = REPO / "data" / "v2_processed" / args.split
    assert "test" not in str(split_dir), "must never read the test split"
    args.out_dir.mkdir(parents=True, exist_ok=True)

    model, ck_names = load_checkpoint(args.weights,
                                      device=resolve_device("auto"))
    names = [str(n) for n in ck_names]
    device = next(model.parameters()).device
    model.eval()

    idx_collie = names.index(COLLIE) if COLLIE in names else -1
    idx_border = names.index(BORDER) if BORDER in names else -1
    if idx_collie < 0 or idx_border < 0:
        print(f"[scan] 类别空间缺少 {COLLIE}/{BORDER}，无法评估", file=sys.stderr)
        return 1

    dataset = datasets.ImageFolder(
        root=str(split_dir),
        transform=build_transforms(train=False, image_size=args.image_size))
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False,
                        num_workers=0)
    classes = dataset.classes

    rows: list[dict] = []
    with torch.no_grad():
        offset = 0
        for images, targets in loader:
            logits = model(images.to(device))
            probs = torch.softmax(logits, dim=1).cpu()
            for i in range(probs.shape[0]):
                p = probs[i]
                top1_idx = int(torch.argmax(p).item())
                p_collie = float(p[idx_collie].item())
                p_border = float(p[idx_border].item())
                pair_mass = p_collie + p_border
                pair_margin = abs(p_collie - p_border)
                share = (min(p_collie, p_border) / pair_mass
                         if pair_mass > 0 else 0.0)
                rel = Path(dataset.samples[offset + i][0])
                rows.append({
                    "image_path": str(rel.relative_to(REPO)).replace("\\", "/"),
                    "true_label": classes[int(targets[i].item())],
                    "top1_label": names[top1_idx],
                    "top1_probability": round(float(p[top1_idx].item()), 8),
                    "p_collie": round(p_collie, 8),
                    "p_border_collie": round(p_border, 8),
                    "pair_mass": round(pair_mass, 8),
                    "pair_margin": round(pair_margin, 8),
                    "pair_share": round(share, 8),
                    "top1_in_pair": names[top1_idx] in (COLLIE, BORDER),
                })
            offset += probs.shape[0]

    print(f"[scan] 共 {len(rows)} 张（split={args.split}, "
          f"image_size={args.image_size}）")

    csv_path = args.out_dir / f"val_pair_{args.image_size}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    target = [r for r in rows if r["true_label"] in (COLLIE, BORDER)]
    top1_in_pair = [r for r in rows if r["top1_in_pair"]]

    # ---- 目标类正确率与相互错分 ----
    def acc(label: str) -> dict:
        sub = [r for r in target if r["true_label"] == label]
        correct = sum(1 for r in sub if r["top1_label"] == label)
        to_other = sum(1 for r in sub
                       if r["top1_label"] == (BORDER if label == COLLIE
                                              else COLLIE))
        return {"support": len(sub), "correct": correct,
                "accuracy": round(correct / len(sub), 6) if sub else 0.0,
                "confused_with_sibling": to_other}

    confusion = {COLLIE: acc(COLLIE), BORDER: acc(BORDER)}

    # ---- 网格：原策略 vs 新策略 ----
    def evaluate(mass_thr: float, predicate) -> dict:
        fired = [r for r in top1_in_pair
                 if r["pair_mass"] >= mass_thr and predicate(r)]
        fired_true_in = [r for r in fired if r["true_label"] in (COLLIE, BORDER)]
        fired_true_out = [r for r in fired if r["true_label"] not in (COLLIE, BORDER)]
        by_label: dict[str, int] = {}
        for r in fired:
            by_label[r["true_label"]] = by_label.get(r["true_label"], 0) + 1
        return {
            "triggered": len(fired),
            "trigger_rate_overall": round(len(fired) / len(rows), 6),
            "triggered_true_in_pair": len(fired_true_in),
            "triggered_true_out_of_pair": len(fired_true_out),
            "true_label_breakdown": by_label,
            "triggered_images": [
                {"image_path": r["image_path"], "true_label": r["true_label"],
                 "top1_label": r["top1_label"],
                 "pair_mass": r["pair_mass"], "pair_margin": r["pair_margin"],
                 "pair_share": r["pair_share"]}
                for r in fired],
        }

    legacy = evaluate(MASS_THRESHOLD,
                      lambda r: r["pair_margin"] <= LEGACY_MARGIN_THRESHOLD)
    grid = {}
    for theta in SHARE_GRID:
        grid[f"{theta:.2f}"] = evaluate(MASS_THRESHOLD,
                                        lambda r, t=theta: r["pair_share"] >= t)

    # 目标类内的份额分布（用于展示间隔）
    share_sorted = sorted(((r["pair_share"], r["image_path"], r["true_label"])
                           for r in target), reverse=True)

    payload = {
        "generated_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "weights": str(args.weights),
        "image_size": args.image_size,
        "split": args.split,
        "split_total": len(rows),
        "test_split_access_count": 0,
        "definition": {
            "pair_mass": "p_collie + p_border_collie（完整 136 维 softmax）",
            "pair_margin": "abs(p_collie - p_border_collie)，v1 使用的绝对分差",
            "pair_share": "min(p_collie, p_border_collie) / pair_mass，"
                          "组内相对份额；与 softmax 绝对尺度无关",
            "precondition": "原始 Top-1 必须属于 {collie, border_collie}",
        },
        "top1_in_pair": {
            "count": len(top1_in_pair),
            "true_pair_total": len(target),
            "note": "前置条件挡住的数量 = true_pair_total - top1_in_pair 中"
                    "真实属于两类的图；用于区分"
                    "『前置条件导致无法触发』与『绝对阈值导致无法触发』",
        },
        "target_class_confusion": confusion,
        "legacy_rule": {
            "rule": f"top1 in pair AND pair_mass >= {MASS_THRESHOLD} "
                    f"AND pair_margin <= {LEGACY_MARGIN_THRESHOLD}",
            **legacy,
        },
        "share_rule_grid": {
            "rule_template": f"top1 in pair AND pair_mass >= {MASS_THRESHOLD} "
                             f"AND pair_share >= theta",
            "grid": grid,
        },
        "target_class_share_distribution": [
            {"pair_share": s, "image_path": p, "true_label": t}
            for s, p, t in share_sorted],
        "evidence_csv": str(csv_path.resolve().relative_to(REPO))
                        .replace("\\", "/"),
    }

    json_path = args.out_dir / "collie_pair_validation.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                         encoding="utf-8")

    print(f"[scan] 目标类 {len(target)} 张，Top-1 在组内 {len(top1_in_pair)} 张")
    print(f"[scan] collie: {confusion[COLLIE]}")
    print(f"[scan] border: {confusion[BORDER]}")
    print(f"[scan] 原策略触发 {legacy['triggered']} 张 "
          f"(组外 {legacy['triggered_true_out_of_pair']})")
    print("[scan] 新策略网格：")
    for theta, res in grid.items():
        print(f"   theta={theta}  触发 {res['triggered']:>3} 张  "
              f"率 {res['trigger_rate_overall']*100:.4f}%  "
              f"真实在组内 {res['triggered_true_in_pair']}  "
              f"组外 {res['triggered_true_out_of_pair']}  "
              f"标签分布 {res['true_label_breakdown']}")
    print(f"[scan] wrote {csv_path} 与 {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
