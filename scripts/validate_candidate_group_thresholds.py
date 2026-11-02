#!/usr/bin/env python
"""候选组触发阈值的 validation-split 验证脚本（只读，不训练）。

用法（在仓库根目录执行）::

    python scripts/validate_candidate_group_thresholds.py

只对 **validation split**（``data/v2_processed/val``，2,079 张）跑一次前向
推理，统计候选组（AmStaff / SBT / American Bulldog）的质量分布与组内分差
分布，扫描阈值网格并写出::

    reports/v2_1_candidate_ui_review/candidate_threshold_validation.csv

**test split 完全不参与选阈值**，也不在本脚本中读取。脚本不训练、不回写
权重、不修改任何数据或标签。
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
from ml.model import load_checkpoint, resolve_device  # noqa: E402

sys.path.insert(0, str(_REPO_ROOT / "backend"))
from backend.app.services.candidate_group import (  # noqa: E402
    CANDIDATE_GROUP,
    MARGIN_THRESHOLD,
    MASS_THRESHOLD,
)

DEFAULT_MODEL_DIR = _REPO_ROOT / "artifacts" / "v2_1_136classes_seed42"
DEFAULT_VAL_DIR = _REPO_ROOT / "data" / "v2_processed" / "val"
DEFAULT_OUT = _REPO_ROOT / "reports" / "v2_1_candidate_ui_review"

#: 阈值扫描网格（仅覆盖 validation split 的统计分布，不用 test 调参）。
MASS_GRID = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)
MARGIN_GRID = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60)

#: 触发覆盖率的目标区间（在"top-1 已落入候选组"的**子总体**上计算）。
#: 验证数据显示该子总体上模型通常很确定（组内分差中位数约 0.76），
#: 因此本特征按设计就是"少数真正歧义时才触发"的兜底提示，目标区间相应放宽。
TARGET_COVERAGE_MIN = 0.05
TARGET_COVERAGE_MAX = 0.50

#: 组内分差阈值的**设计上限**。原始概率差超过该值就不应再视为"难以区分"，
#: 否则会把模型已有明确偏好的样本也硬塞进候选组，违背任务口径。
MAX_MARGIN_ALLOWED = 0.40


def infer_val(model, val_dir: Path, class_names: list[str], device,
              batch_size: int = 32) -> list[dict]:
    """对 validation split 跑一次前向，返回逐图 Top-3 与候选组概率。"""
    paths = sorted(val_dir.rglob("*.jpg"))
    if not paths:
        raise ValueError(f"no validation images under {val_dir}")
    transform = build_transforms(train=False)
    index_of = {name: i for i, name in enumerate(class_names)}
    group_indices = [index_of[label] for label in CANDIDATE_GROUP
                     if label in index_of]
    if len(group_indices) < 2:
        raise ValueError(
            f"model class space lacks the candidate group: {CANDIDATE_GROUP}")

    rows: list[dict] = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(paths), batch_size):
            chunk = paths[start:start + batch_size]
            tensors = []
            for path in chunk:
                with Image.open(path) as image:
                    tensors.append(transform(image.convert("RGB")))
            logits = model(torch.stack(tensors).to(device))
            probs = torch.softmax(logits, dim=1).cpu().numpy()
            for offset, probability in enumerate(probs):
                order = np.argsort(-probability)
                top3 = [(class_names[int(i)], float(probability[int(i)]))
                        for i in order[:3]]
                group_probs = {label: float(probability[index_of[label]])
                               for label in CANDIDATE_GROUP
                               if label in index_of}
                rows.append({
                    "image": str(chunk[offset]),
                    "true_label": chunk[offset].parent.name,
                    "top1": top3[0][0],
                    "top1_prob": top3[0][1],
                    "top2": top3[1][0],
                    "top2_prob": top3[1][1],
                    "top3": top3[2][0],
                    "top3_prob": top3[2][1],
                    "group_probs": group_probs,
                })
    print(f"[threshold] inferred {len(rows)} validation images")
    return rows


def evaluate_grid(rows: list[dict]) -> list[dict]:
    """扫描 (mass, margin) 阈值网格，统计触发覆盖率与构成。

    覆盖率的分母是 **top-1 已落入候选组的子总体**（记为
    ``subpopulation``）——这是任务规则（"top-1 在候选组内"）天然限定的
    范围；同时给出相对全部验证图的覆盖率便于横向对比。
    """
    results = []
    subpopulation = [row for row in rows
                     if row["top1"] in CANDIDATE_GROUP]
    total = len(rows)
    sub_total = len(subpopulation)
    for mass in MASS_GRID:
        for margin in MARGIN_GRID:
            triggered = []
            for row in subpopulation:
                group_probs = row["group_probs"]
                group_mass = sum(group_probs.values())
                ranked = sorted(group_probs.values(), reverse=True)
                group_margin = (ranked[0] - ranked[1]) if len(ranked) > 1 else 0.0
                if group_mass >= mass and group_margin <= margin:
                    triggered.append(row)
            coverage = (len(triggered) / sub_total) if sub_total else 0.0
            # 触发样本的真实标签构成（用于判断"误触发"）
            true_in_group = sum(1 for r in triggered
                                if r["true_label"] in CANDIDATE_GROUP)
            results.append({
                "mass_threshold": mass,
                "margin_threshold": margin,
                "triggered_count": len(triggered),
                "subpopulation": sub_total,
                "coverage_of_subpopulation": round(coverage, 6),
                "coverage_of_all_val": round(len(triggered) / total, 6)
                if total else 0.0,
                "true_label_in_group": true_in_group,
                "true_label_in_group_ratio": round(
                    true_in_group / len(triggered), 6) if triggered else 0.0,
                "top1_of_triggered": "; ".join(
                    f"{name}:{count}" for name, count in sorted(
                        CounterNames(r["top1"] for r in triggered).items())),
            })
    return results


def CounterNames(values) -> dict:
    from collections import Counter
    return dict(Counter(values))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--val-dir", type=Path, default=DEFAULT_VAL_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args(argv)

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    device = resolve_device(args.device)
    model, class_names = load_checkpoint(
        args.model_dir / "best_model.pth", device=device)
    if len(class_names) != 136:
        print(f"[threshold] expected 136 classes, got {len(class_names)}",
              file=sys.stderr)
        return 1
    print(f"[threshold] device={device} classes={len(class_names)}")

    rows = infer_val(model, args.val_dir, class_names, device)
    grid = evaluate_grid(rows)

    csv_path = out_dir / "candidate_threshold_validation.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(grid[0].keys()))
        writer.writeheader()
        writer.writerows(grid)
    print(f"[threshold] wrote {csv_path}")

    # ---- 汇总统计（写进报告用）----
    # 全体验证图上的分布（绝大多数图三个候选概率都接近 0）。
    masses_all = np.array([sum(r["group_probs"].values()) for r in rows])
    # 子总体：top-1 已落入候选组的图片——阈值应在这个子总体上选择。
    sub_rows = [row for row in rows if row["top1"] in CANDIDATE_GROUP]
    masses = np.array([sum(r["group_probs"].values()) for r in sub_rows])
    margins = []
    for row in sub_rows:
        values = sorted(row["group_probs"].values(), reverse=True)
        margins.append(values[0] - values[1] if len(values) > 1 else 0.0)
    margins = np.array(margins)
    top1_in_group = len(sub_rows)

    def _dist(array: np.ndarray) -> dict:
        if array.size == 0:
            return {"n": 0}
        return {
            "n": int(array.size),
            "min": round(float(array.min()), 6),
            "p25": round(float(np.percentile(array, 25)), 6),
            "median": round(float(np.median(array)), 6),
            "p75": round(float(np.percentile(array, 75)), 6),
            "p90": round(float(np.percentile(array, 90)), 6),
            "max": round(float(array.max()), 6),
        }

    # 只在"分差不超过设计上限"的组合里选，避免把模型已明确的样本算成歧义。
    in_target = [item for item in grid
                 if item["margin_threshold"] <= MAX_MARGIN_ALLOWED
                 and TARGET_COVERAGE_MIN <= item["coverage_of_subpopulation"]
                 <= TARGET_COVERAGE_MAX]
    chosen = None
    if in_target:
        # 先看"触发的样本里真标签确实在组内"的比例（越可能是真相近品种），
        # 其次看触发数量（覆盖不能太低），最后在同等效果下取更严格的
        # 质量门槛（更不容易误触发）。
        chosen = max(in_target, key=lambda item: (
            item["true_label_in_group_ratio"], item["triggered_count"],
            item["mass_threshold"]))
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_dir": str(args.model_dir),
        "val_dir": str(args.val_dir),
        "val_images": len(rows),
        "split_used": "validation only (test split never read)",
        "candidate_group": list(CANDIDATE_GROUP),
        "top1_in_candidate_group": top1_in_group,
        "top1_in_candidate_group_ratio": round(top1_in_group / len(rows), 6),
        "group_mass_distribution_all_val": _dist(masses_all),
        "group_mass_distribution_subpopulation": _dist(masses),
        "group_margin_distribution_subpopulation": _dist(margins),
        "target_coverage_range_of_subpopulation": [TARGET_COVERAGE_MIN,
                                                   TARGET_COVERAGE_MAX],
        "current_module_thresholds": {
            "mass": MASS_THRESHOLD, "margin": MARGIN_THRESHOLD},
        "chosen_thresholds": chosen,
        "grid_rows": len(grid),
    }
    summary_path = out_dir / "candidate_threshold_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                            encoding="utf-8")
    print(f"[threshold] wrote {summary_path}")
    print()
    print(f"[threshold] val 图片 {len(rows)} 张；top-1 落入候选组 "
          f"{top1_in_group} 张（{top1_in_group / len(rows):.2%}）")
    if top1_in_group:
        print(f"[threshold] 子总体({top1_in_group} 张)组内总质量中位数 "
              f"{summary['group_mass_distribution_subpopulation']['median']:.4f}，"
              f"组内分差中位数 "
              f"{summary['group_margin_distribution_subpopulation']['median']:.4f}")
    if chosen:
        print(f"[threshold] 建议阈值: mass>={chosen['mass_threshold']} "
              f"margin<={chosen['margin_threshold']}  "
              f"子总体覆盖率 {chosen['coverage_of_subpopulation']:.2%}"
              f"（全体验证图 {chosen['coverage_of_all_val']:.2%}），"
              f"触发中真标签在组内占 {chosen['true_label_in_group_ratio']:.2%}")
    else:
        print("[threshold] 目标覆盖区间内无合适阈值组合，需人工判断")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
