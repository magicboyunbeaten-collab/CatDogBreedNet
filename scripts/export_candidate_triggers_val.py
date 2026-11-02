#!/usr/bin/env python
"""导出 validation split 上实际触发相近犬种候选组的图片清单（只读）。

用法（在仓库根目录执行）::

    python scripts/export_candidate_triggers_val.py

对 ``data/v2_processed/val``（2,079 张）跑**一次**前向推理，然后用**线上同一个
函数** ``backend.app.services.candidate_group.build_candidate_group``（模块
默认阈值，不注入自定义值）判定是否触发，导出：

* ``val_candidate_triggers.csv`` —— 实际触发的图片清单；
* ``val_candidate_group_stats.json`` —— 汇总统计（含未触发原因分布）。

**只读 validation split，不读取 test split，不调整任何阈值。**
不训练、不回写权重、不修改数据或标签。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
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
    CANDIDATE_GROUP_ZH,
    MARGIN_THRESHOLD,
    MASS_THRESHOLD,
    THRESHOLD_VERSION,
    build_candidate_group,
)

DEFAULT_MODEL_DIR = _REPO_ROOT / "artifacts" / "v2_1_136classes_seed42"
DEFAULT_VAL_DIR = _REPO_ROOT / "data" / "v2_processed" / "val"
DEFAULT_OUT = _REPO_ROOT / "reports" / "v2_1_candidate_ui_review"


def infer_val(model, val_dir: Path, class_names: list[str], device,
              batch_size: int = 32) -> list[dict]:
    """对 validation split 跑一次前向，返回逐图 Top-3 与三候选原始概率。"""
    paths = sorted(val_dir.rglob("*.jpg"))
    if not paths:
        raise ValueError(f"no validation images under {val_dir}")
    transform = build_transforms(train=False)
    index_of = {name: i for i, name in enumerate(class_names)}
    group_indices = [index_of[label] for label in CANDIDATE_GROUP
                     if label in index_of]
    if len(group_indices) < len(CANDIDATE_GROUP):
        raise ValueError(
            f"model class space lacks part of the candidate group: "
            f"{CANDIDATE_GROUP}")

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
                rows.append({
                    "image": str(chunk[offset]),
                    "true_label": chunk[offset].parent.name,
                    "top1": top3[0][0],
                    "top1_prob": top3[0][1],
                    "top2": top3[1][0],
                    "top2_prob": top3[1][1],
                    "top3": top3[2][0],
                    "top3_prob": top3[2][1],
                    "group_probs": {label: float(probability[index_of[label]])
                                    for label in CANDIDATE_GROUP},
                })
    print(f"[triggers] inferred {len(rows)} validation images")
    return rows


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
        print(f"[triggers] expected 136 classes, got {len(class_names)}",
              file=sys.stderr)
        return 1
    print(f"[triggers] device={device} classes={len(class_names)}")
    print(f"[triggers] thresholds: mass>={MASS_THRESHOLD} "
          f"margin<={MARGIN_THRESHOLD} version={THRESHOLD_VERSION}")

    rows = infer_val(model, args.val_dir, class_names, device)

    # ---- 用线上同一函数逐图判定（与 API 链路一致：传入完整概率向量）----
    triggered_rows: list[dict] = []
    reason_counter: Counter = Counter()
    for row in rows:
        predictions = [
            {"breed": row["top1"], "confidence": row["top1_prob"]},
            {"breed": row["top2"], "confidence": row["top2_prob"]},
            {"breed": row["top3"], "confidence": row["top3_prob"]},
        ]
        # 完整 softmax 向量，避免候选因排名低于 top-3 被当作 0 分
        probabilities = dict(row["group_probs"])
        group = build_candidate_group(predictions, class_names=class_names,
                                      probabilities=probabilities)
        if group is None:
            reason_counter["候选组在当前类别空间不完整"] += 1
            continue
        if group["triggered"]:
            triggered_rows.append({**row, "group": group})
        else:
            reason_counter[group["reason"].split("，")[0]] += 1

    # ---- 导出触发清单 ----
    fieldnames = [
        "image_path", "true_label", "top1_breed", "top1_confidence",
        "top2_breed", "top2_confidence",
        "prob_american_staffordshire_terrier",
        "prob_staffordshire_bull_terrier",
        "prob_american_bulldog",
        "group_score_american_staffordshire_terrier",
        "group_score_staffordshire_bull_terrier",
        "group_score_american_bulldog",
        "group_mass", "group_margin", "triggered", "reason",
        "threshold_version",
    ]
    csv_path = out_dir / "val_candidate_triggers.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in triggered_rows:
            group = row["group"]
            scores = {item["breed"]: item["group_score"]
                      for item in group["candidates"]}
            writer.writerow({
                "image_path": row["image"],
                "true_label": row["true_label"],
                "top1_breed": group["top1_breed"],
                "top1_confidence": group["top1_confidence"],
                "top2_breed": row["top2"],
                "top2_confidence": round(row["top2_prob"], 6),
                "prob_american_staffordshire_terrier":
                    row["group_probs"]["american_staffordshire_terrier"],
                "prob_staffordshire_bull_terrier":
                    row["group_probs"]["staffordshire_bull_terrier"],
                "prob_american_bulldog": row["group_probs"]["american_bulldog"],
                "group_score_american_staffordshire_terrier":
                    scores["american_staffordshire_terrier"],
                "group_score_staffordshire_bull_terrier":
                    scores["staffordshire_bull_terrier"],
                "group_score_american_bulldog":
                    scores["american_bulldog"],
                "group_mass": group["group_mass"],
                "group_margin": group["group_margin"],
                "triggered": group["triggered"],
                "reason": group["reason"],
                "threshold_version": group["threshold_version"],
            })
    print(f"[triggers] wrote {csv_path}")

    # ---- 汇总统计 ----
    top1_in_group = sum(1 for r in rows if r["top1"] in CANDIDATE_GROUP)
    top1_apbt = sum(1 for r in rows
                    if r["top1"] == "american_pit_bull_terrier")
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_dir": str(args.model_dir),
        "val_dir": str(args.val_dir),
        "split_used": "validation only (test split never read)",
        "val_images": len(rows),
        "thresholds": {"mass": MASS_THRESHOLD, "margin": MARGIN_THRESHOLD,
                       "version": THRESHOLD_VERSION},
        "candidate_group": list(CANDIDATE_GROUP),
        "candidate_group_zh": CANDIDATE_GROUP_ZH,
        "top1_in_candidate_group": top1_in_group,
        "top1_in_candidate_group_ratio": round(top1_in_group / len(rows), 6),
        "top1_american_pit_bull_terrier": top1_apbt,
        "top1_american_pit_bull_terrier_ratio": round(top1_apbt / len(rows), 6),
        "triggered_count": len(triggered_rows),
        "triggered_ratio_of_val": round(len(triggered_rows) / len(rows), 6),
        "triggered_true_labels": dict(Counter(r["true_label"]
                                              for r in triggered_rows)),
        "not_triggered_reasons": dict(reason_counter),
    }
    summary_path = out_dir / "val_candidate_group_stats.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                            encoding="utf-8")
    print(f"[triggers] wrote {summary_path}")
    print()
    print(f"[triggers] val {len(rows)} 张；top-1 落入候选组 {top1_in_group} 张；"
          f"top-1 为 APBT {top1_apbt} 张")
    print(f"[triggers] **实际触发 {len(triggered_rows)} 张**"
          f"（占 val {len(triggered_rows) / len(rows):.2%}）")
    for label, count in sorted(Counter(r["true_label"]
                                       for r in triggered_rows).items()):
        print(f"    {label:<34} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
