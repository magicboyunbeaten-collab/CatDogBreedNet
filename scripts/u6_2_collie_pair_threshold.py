#!/usr/bin/env python
"""U6.2：柯利牧羊犬 / 边境牧羊犬双候选提示的 validation 阈值扫描。

用法（在仓库根目录执行）::

    python scripts/u6_2_collie_pair_threshold.py

设计要点
--------
* **只读**：仅加载冻结的 V2.1 checkpoint 与 136 类映射，仅 ``rglob``
  ``data/v2_processed/val``；脚本内不含任何 test 路径。
* **一次前向**：内存中保留完整 136 维 softmax；落盘只写
  ``p_collie`` / ``p_border_collie`` / top-1 / top-5，**不对外暴露全量概率**。
* **网格扫描**：``mass`` 7 档 × ``margin`` 8 档 = 56 组合，逐组统计
  任务 §2.2 要求的全部指标（含分子/分母）。
* **触发语义**：三者同时满足才触发 —— Top-1 ∈ {collie, border_collie}、
  ``pair_mass >= mass``、``pair_margin = abs(p_collie - p_border_collie) <= margin``。

产出（``reports/u6_2_collie_pair_candidate/``）：

* ``validation_threshold_grid.csv`` —— 56 行，每行一个组合的全部统计
* ``validation_trigger_samples.csv`` —— 所有触发图的逐图明细
* ``u6_2_threshold_scan.json`` —— 汇总与阈值选择建议
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ml.dataset import build_transforms  # noqa: E402
from ml.model import load_checkpoint  # noqa: E402

OUT_DIR = _REPO_ROOT / "reports" / "u6_2_collie_pair_candidate"
V21_DIR = _REPO_ROOT / "artifacts" / "v2_1_136classes_seed42"
VAL_DIR = _REPO_ROOT / "data" / "v2_processed" / "val"

PAIR = ("collie", "border_collie")

MASS_GRID = (0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)
MARGIN_GRID = (0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40)


def infer_val(batch_size: int = 32) -> tuple[list[dict], list[str]]:
    """对 validation 跑一次前向，返回逐图记录与类别名（内存含完整概率）。"""
    weights = V21_DIR / "best_model.pth"
    class_names_path = V21_DIR / "class_names.json"
    saved = json.loads(class_names_path.read_text(encoding="utf-8"))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, ckpt_names = load_checkpoint(weights, device=device)
    if list(ckpt_names) != list(saved):
        raise ValueError("checkpoint 与 class_names.json 类别顺序不一致")
    class_names = list(ckpt_names)
    index_of = {name: i for i, name in enumerate(class_names)}

    model.eval()
    transform = build_transforms(train=False)
    samples: list[tuple[Path, int]] = []
    for name in class_names:
        class_dir = VAL_DIR / name
        if not class_dir.is_dir():
            raise FileNotFoundError(f"missing class directory: {class_dir}")
        for image_path in sorted(class_dir.glob("*.jpg")):
            samples.append((image_path, index_of[name]))

    rows: list[dict] = []
    with torch.inference_mode():
        for start in range(0, len(samples), batch_size):
            batch = samples[start:start + batch_size]
            tensors = []
            for image_path, _ in batch:
                with Image.open(image_path) as image:
                    tensors.append(transform(image.convert("RGB")))
            logits = model(torch.stack(tensors).to(device))
            probs = torch.softmax(logits, dim=1).cpu().numpy()
            for offset, (image_path, true_index) in enumerate(batch):
                prob = probs[offset]
                top5 = np.argsort(-prob)[:5]
                rows.append({
                    "image_path": image_path.relative_to(
                        VAL_DIR.parent).as_posix(),
                    "true_label": class_names[true_index],
                    "top1_label": class_names[int(top5[0])],
                    "top1_probability": round(float(prob[top5[0]]), 8),
                    "p_collie": round(float(prob[index_of["collie"]]), 8),
                    "p_border_collie": round(
                        float(prob[index_of["border_collie"]]), 8),
                    "top5": ";".join(
                        f"{class_names[int(j)]}:{prob[j]:.6f}" for j in top5),
                })
    return rows, class_names


def grid_scan(rows: list[dict]) -> list[dict]:
    """对 56 个阈值组合逐组统计任务 §2.2 要求的指标。"""
    total = len(rows)
    pair_subset = [r for r in rows if r["top1_label"] in PAIR]
    true_pair = [r for r in rows if r["true_label"] in PAIR]
    true_counts = {label: sum(1 for r in rows if r["true_label"] == label)
                   for label in PAIR}

    grid: list[dict] = []
    for mass in MASS_GRID:
        for margin in MARGIN_GRID:
            triggered = [
                r for r in pair_subset
                if r["p_collie"] + r["p_border_collie"] >= mass
                and abs(r["p_collie"] - r["p_border_collie"]) <= margin
            ]
            in_group = [r for r in triggered if r["true_label"] in PAIR]
            out_group = [r for r in triggered if r["true_label"] not in PAIR]
            out_labels = sorted({r["true_label"] for r in out_group})
            per_true = {
                label: sum(1 for r in triggered if r["true_label"] == label)
                for label in PAIR
            }
            grid.append({
                "pair_mass_threshold": mass,
                "pair_margin_threshold": margin,
                "val_total": total,
                "top1_in_pair_subset": len(pair_subset),
                "triggered_count": len(triggered),
                "trigger_rate_overall": round(len(triggered) / total, 6),
                "trigger_rate_within_top1_pair_subset": round(
                    len(triggered) / len(pair_subset), 6) if pair_subset else "",
                "triggered_true_in_pair": len(in_group),
                "triggered_true_in_pair_ratio": round(
                    len(in_group) / len(triggered), 6) if triggered else "",
                "triggered_true_out_of_pair": len(out_group),
                "triggered_true_out_of_pair_ratio": round(
                    len(out_group) / len(triggered), 6) if triggered else "",
                "triggered_out_of_pair_labels": ";".join(out_labels),
                "true_collie_total": true_counts["collie"],
                "true_border_collie_total": true_counts["border_collie"],
                "true_collie_triggered": per_true["collie"],
                "true_border_collie_triggered": per_true["border_collie"],
                "true_pair_total": len(true_pair),
                "true_pair_recall": round(
                    len(in_group) / len(true_pair), 6) if true_pair else "",
            })
    return grid


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[u6.2] 只读加载 V2.1：{V21_DIR / 'best_model.pth'}")
    rows, class_names = infer_val(batch_size=args.batch_size)
    print(f"[u6.2] val 推理完成：{len(rows)} 张，{len(class_names)} 类")

    # ---- 触发图逐图明细（取最宽松组合以便观察全貌，同时记录各档判定）----
    detail_rows = []
    for row in rows:
        if row["top1_label"] not in PAIR:
            continue
        pair_mass = round(row["p_collie"] + row["p_border_collie"], 8)
        pair_margin = round(abs(row["p_collie"] - row["p_border_collie"]), 8)
        detail_rows.append({
            "image_path": row["image_path"],
            "true_label": row["true_label"],
            "top1_label": row["top1_label"],
            "top1_probability": row["top1_probability"],
            "p_collie": row["p_collie"],
            "p_border_collie": row["p_border_collie"],
            "pair_mass": pair_mass,
            "pair_margin": pair_margin,
            "true_label_in_pair": "yes" if row["true_label"] in PAIR else "no",
            "top5": row["top5"],
        })

    grid = grid_scan(rows)
    grid_path = out_dir / "validation_threshold_grid.csv"
    with grid_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(grid[0].keys()))
        writer.writeheader()
        writer.writerows(grid)

    detail_path = out_dir / "validation_trigger_samples.csv"
    with detail_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(detail_rows[0].keys()))
        writer.writeheader()
        writer.writerows(detail_rows)

    # ---- 控制台摘要 ----
    subset = len([r for r in rows if r["top1_label"] in PAIR])
    true_pair = len([r for r in rows if r["true_label"] in PAIR])
    print(f"[u6.2] Top-1 属两类的子集：{subset} 张；"
          f"真实标签属两类的样本：{true_pair} 张")
    print(f"[u6.2] wrote {grid_path}（{len(grid)} 组合）")
    print(f"[u6.2] wrote {detail_path}（{len(detail_rows)} 张 Top-1 属两类的图）")

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weights": str(V21_DIR / "best_model.pth"),
        "class_names": str(V21_DIR / "class_names.json"),
        "val_images": len(rows),
        "num_classes": len(class_names),
        "test_split_access_count": 0,
        "top1_in_pair_subset": subset,
        "true_pair_total": true_pair,
        "mass_grid": list(MASS_GRID),
        "margin_grid": list(MARGIN_GRID),
        "grid_combinations": len(grid),
    }
    (out_dir / "u6_2_threshold_scan.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[u6.2] wrote {out_dir / 'u6_2_threshold_scan.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
