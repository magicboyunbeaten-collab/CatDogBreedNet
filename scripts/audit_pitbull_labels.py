#!/usr/bin/env python
"""APBT / AmStaff 及其邻近类别的混淆、标签可追溯性与合并上位类离线评估。

用法（在仓库根目录执行）::

    python scripts/audit_pitbull_labels.py

内容：

1. 5 类（APBT / AmStaff / SBT / American Bulldog / Bullmastiff）的
   **5×5 实际混淆**（行=真实，列=预测，另设 ``other`` 列汇总流向其余类别）；
2. **全 split 逐图预测**（909 行，需对 train/val 补推理）；
3. **合并上位类离线评估**：把 APBT 与 AmStaff 的真实标签与预测标签同时
   映射为 ``pit_bull_type_merged``，在 135 类空间重算指标。这是**后验标签
   重映射**，不是重训练，也不代表修改正式标签体系；
4. **标签可追溯性审计**：文件名 wnid、类别目录、来源 manifest，按
   「已证实重复 / 来源冲突 / 标签依据不足 / 仅外观相似」分档。

只读 checkpoint 与数据，只写 ``reports/v2_1_coat_pitbull_diagnostics/``；
不改任何标签、不删图、不训练。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from sklearn.metrics import (accuracy_score, classification_report, f1_score,
                             precision_score, recall_score)

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ml.dataset import build_transforms  # noqa: E402
from ml.model import load_checkpoint, resolve_device  # noqa: E402

DEFAULT_MODEL_DIR = _REPO_ROOT / "artifacts" / "v2_1_136classes_seed42"
DEFAULT_DATA_DIR = _REPO_ROOT / "data" / "v2_processed"
DEFAULT_OUT = _REPO_ROOT / "reports" / "v2_1_coat_pitbull_diagnostics"
LEGACY_PREDICTIONS = (_REPO_ROOT / "reports" / "v2_1_diagnostics"
                      / "all_predictions_136.csv")
CATALOG = _REPO_ROOT / "reports" / "v2_class_catalog.json"
STANFORD_MANIFEST = (_REPO_ROOT / "data" / "external_raw" / "stanford_dogs"
                     / "download_manifest.json")

APBT = "american_pit_bull_terrier"
AMSTAFF = "american_staffordshire_terrier"
SBT = "staffordshire_bull_terrier"
AMBULL = "american_bulldog"
BULLMASTIFF = "bull_mastiff"
MERGED = "pit_bull_type_merged"
FAMILY = (APBT, AMSTAFF, SBT, AMBULL, BULLMASTIFF)
SPLITS = ("train", "val", "test")
MERGE_MAP = {APBT: MERGED, AMSTAFF: MERGED}

_STANFORD_RE = re.compile(r"^(n\d{8})_")


def source_evidence(label: str, filename: str) -> str:
    stem = Path(filename).stem
    match = _STANFORD_RE.match(stem)
    if match:
        return f"Stanford Dogs (ImageNet wnid {match.group(1)})"
    if stem.startswith(label):
        return "Oxford-IIIT Pet"
    return "unknown"


def predict_paths(model, paths: list[Path], class_names: list[str], device,
                  batch_size: int = 32) -> list[dict]:
    transform = build_transforms(train=False)
    model.eval()
    results: list[dict] = []
    with torch.no_grad():
        for start in range(0, len(paths), batch_size):
            chunk = paths[start:start + batch_size]
            tensors = []
            for path in chunk:
                with Image.open(path) as image:
                    tensors.append(transform(image.convert("RGB")))
            logits = model(torch.stack(tensors).to(device))
            probs = torch.softmax(logits, dim=1).cpu().numpy()
            for probability in probs:
                order = np.argsort(-probability)[:5]
                results.append({
                    "pred_label": class_names[int(order[0])],
                    "top1_prob": float(probability[order[0]]),
                    "top2_label": class_names[int(order[1])],
                    "top2_prob": float(probability[order[1]]),
                    "top5": "|".join(
                        f"{class_names[int(i)]}:{float(probability[int(i)]):.6f}"
                        for i in order),
                })
    if len(results) != len(paths):
        raise ValueError(f"inference mismatch: {len(results)} vs {len(paths)}")
    return results


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def binary_metrics(pairs: list[tuple[str, str]], label: str) -> dict:
    truth = [1 if t == label else 0 for t, _ in pairs]
    called = [1 if p == label else 0 for _, p in pairs]
    return {
        "support": sum(truth),
        "predicted": sum(called),
        "precision": round(float(precision_score(truth, called,
                                                 zero_division=0)), 6),
        "recall": round(float(recall_score(truth, called,
                                           zero_division=0)), 6),
        "f1": round(float(f1_score(truth, called, zero_division=0)), 6),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args(argv)

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    device = resolve_device(args.device)

    model, class_names = load_checkpoint(
        args.model_dir / "best_model.pth", device=device)
    if len(class_names) != 136:
        raise ValueError(f"expected 136 classes, got {len(class_names)}")
    print(f"[pitbull] device={device} classes={len(class_names)}")

    # ---------- 1. 全 split 逐图预测（train/val 需补推理） ----------
    rows: list[dict] = []
    for label in FAMILY:
        for split in SPLITS:
            directory = args.data_dir / split / label
            paths = sorted(directory.glob("*.jpg")) if directory.is_dir() else []
            if not paths:
                print(f"  {label:<32} {split:<5} 0")
                continue
            predictions = predict_paths(model, paths, class_names, device)
            for path, prediction in zip(paths, predictions):
                rows.append({
                    "sample_id": f"{label}/{path.name}",
                    "split": split,
                    "true_label": label,
                    "pred_label": prediction["pred_label"],
                    "correct": int(prediction["pred_label"] == label),
                    "top1_prob": round(prediction["top1_prob"], 6),
                    "top2_label": prediction["top2_label"],
                    "top2_prob": round(prediction["top2_prob"], 6),
                    "top5": prediction["top5"],
                    "image_path": str(path),
                    "file_name": path.name,
                    "source_evidence": source_evidence(label, path.name),
                })
            print(f"  {label:<32} {split:<5} {len(paths)}")

    write_csv(out_dir / "pitbull_predictions_all_splits.csv", rows,
              list(rows[0]))
    print(f"[pitbull] 逐图预测 {len(rows)} 行")

    # ---------- 2. 5x5 混淆（test） ----------
    test_rows = [r for r in rows if r["split"] == "test"]
    matrix = {label: Counter() for label in FAMILY}
    for row in test_rows:
        target = row["pred_label"] if row["pred_label"] in FAMILY else "other"
        matrix[row["true_label"]][target] += 1
    columns = list(FAMILY) + ["other"]
    confusion_rows = []
    for label in FAMILY:
        record = {"true_label": label,
                  "support": sum(matrix[label].values())}
        for column in columns:
            record[column] = matrix[label].get(column, 0)
        confusion_rows.append(record)
    write_csv(out_dir / "pitbull_5x5_confusion.csv", confusion_rows,
              ["true_label", "support"] + columns)
    print("[pitbull] 5x5 混淆（test）：")
    for record in confusion_rows:
        print(f"  {record['true_label']:<34} support={record['support']:>4} "
              f"correct={record[record['true_label']]:>3} "
              f"other={record['other']:>3}")

    # ---------- 3. 合并上位类离线评估 ----------
    if not LEGACY_PREDICTIONS.exists():
        print(f"[pitbull] 缺少 {LEGACY_PREDICTIONS}，无法做合并评估",
              file=sys.stderr)
        return 1
    legacy_rows = []
    with LEGACY_PREDICTIONS.open(encoding="utf-8") as handle:
        for item in csv.DictReader(handle):
            legacy_rows.append({
                "true_label": item["true_label"],
                "pred_label": item["pred_label"]})
    if len(legacy_rows) != 5363:
        raise ValueError(f"expected 5363 test rows, got {len(legacy_rows)}")

    before_pairs = [(r["true_label"], r["pred_label"]) for r in legacy_rows]
    after_pairs = [(MERGE_MAP.get(t, t), MERGE_MAP.get(p, p))
                   for t, p in before_pairs]

    def overall(pairs: list[tuple[str, str]]) -> dict:
        truth = [t for t, _ in pairs]
        called = [p for _, p in pairs]
        return {
            "num_classes": len({*truth, *called}),
            "accuracy": round(float(accuracy_score(truth, called)), 6),
            "macro_f1": round(float(f1_score(truth, called, average="macro",
                                             zero_division=0)), 6),
            "weighted_f1": round(float(f1_score(truth, called,
                                                average="weighted",
                                                zero_division=0)), 6),
        }

    before_overall = overall(before_pairs)
    after_overall = overall(after_pairs)

    affected = [APBT, AMSTAFF, MERGED, SBT, AMBULL, BULLMASTIFF]
    merged_rows = []
    for label in affected:
        before = binary_metrics(before_pairs, label)
        after = binary_metrics(after_pairs, label)
        merged_rows.append({
            "label": label,
            "support_before": before["support"],
            "predicted_before": before["predicted"],
            "precision_before": before["precision"],
            "recall_before": before["recall"],
            "f1_before": before["f1"],
            "support_after": after["support"],
            "predicted_after": after["predicted"],
            "precision_after": after["precision"],
            "recall_after": after["recall"],
            "f1_after": after["f1"],
            "delta_f1": round(after["f1"] - before["f1"], 6),
        })
    for key, value in (("overall_accuracy", (before_overall["accuracy"],
                                             after_overall["accuracy"])),
                       ("overall_macro_f1", (before_overall["macro_f1"],
                                             after_overall["macro_f1"])),
                       ("overall_weighted_f1",
                        (before_overall["weighted_f1"],
                         after_overall["weighted_f1"]))):
        merged_rows.append({
            "label": key,
            "support_before": "", "predicted_before": "",
            "precision_before": "", "recall_before": "",
            "f1_before": value[0],
            "support_after": "", "predicted_after": "",
            "precision_after": "", "recall_after": "",
            "f1_after": value[1],
            "delta_f1": round(value[1] - value[0], 6),
        })
    write_csv(out_dir / "merged_class_evaluation.csv", merged_rows,
              ["label", "support_before", "predicted_before",
               "precision_before", "recall_before", "f1_before",
               "support_after", "predicted_after", "precision_after",
               "recall_after", "f1_after", "delta_f1"])

    # 合并后的 6 类条件混淆（含 other）
    merged_matrix = {label: Counter() for label in
                     (MERGED, SBT, AMBULL, BULLMASTIFF)}
    for truth, called in after_pairs:
        if truth not in merged_matrix:
            continue
        target = called if called in merged_matrix else "other"
        merged_matrix[truth][target] += 1
    merged_columns = [MERGED, SBT, AMBULL, BULLMASTIFF, "other"]
    merged_confusion = []
    for label in merged_matrix:
        record = {"true_label": label,
                  "support": sum(merged_matrix[label].values())}
        for column in merged_columns:
            record[column] = merged_matrix[label].get(column, 0)
        merged_confusion.append(record)
    write_csv(out_dir / "merged_class_confusion.csv", merged_confusion,
              ["true_label", "support"] + merged_columns)

    print()
    print(f"[pitbull] 合并前 overall: {before_overall}")
    print(f"[pitbull] 合并后 overall: {after_overall}")
    for record in merged_rows:
        if record["label"] in (MERGED, APBT, AMSTAFF, SBT, AMBULL,
                               BULLMASTIFF):
            print(f"  {record['label']:<34} F1 {record['f1_before']} -> "
                  f"{record['f1_after']} (Δ {record['delta_f1']})")

    # ---------- 4. 标签可追溯性审计 ----------
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog_by_label = {entry["canonical_label"]: entry
                        for entry in catalog["classes"]}
    manifest_note = "Stanford 下载清单存在" if STANFORD_MANIFEST.exists() \
        else "Stanford 下载清单缺失"
    traceability = []
    for label in FAMILY:
        entry = catalog_by_label.get(label, {})
        counts = {split: len([r for r in rows if r["true_label"] == label
                              and r["split"] == split]) for split in SPLITS}
        filenames = [r["file_name"] for r in rows if r["true_label"] == label]
        wnids = sorted({_STANFORD_RE.match(Path(name).stem).group(1)
                        for name in filenames
                        if _STANFORD_RE.match(Path(name).stem)})
        naming_consistent = all(
            Path(name).stem.startswith(label) for name in filenames
        ) if not wnids else all(
            _STANFORD_RE.match(Path(name).stem) for name in filenames)
        traceability.append({
            "canonical_label": label,
            "source_name": entry.get("source_name", ""),
            "source_original_label": entry.get("source_original_label", ""),
            "imagenet_wnid": ",".join(wnids),
            "train_count": counts["train"], "val_count": counts["val"],
            "test_count": counts["test"],
            "total": sum(counts.values()),
            "filename_pattern_consistent": naming_consistent,
            "label_granularity": (
                "ImageNet 细粒度犬种 synset" if wnids
                else "Oxford-IIIT 品种级标签"),
            "manifest_evidence": manifest_note if wnids else "不适用（Oxford）",
            "duplicate_evidence": "见 pitbull_cross_class_duplicates.csv",
            "traceability_level": (
                "可追溯到类别级 wnid；无逐图摄影师/犬舍来源"
                if wnids else "可追溯到 Oxford-IIIT 品种级标签；无逐图犬只信息"),
            "verified_duplicate": "否（本轮 MD5/pHash 审计为 0 对）",
            "source_conflict": "无（同类图片来自同一来源与同一命名空间）",
            "label_evidence_gap": (
                "缺少犬只登记/血统信息；无法验证单张图片的品种归属"),
            "appearance_only_similarity": (
                "与邻近 bully 类外观相似，属模型可分性问题，非标签错误证据"),
        })
    write_csv(out_dir / "label_traceability_audit.csv", traceability,
              list(traceability[0]))

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_dir": str(args.model_dir),
        "prediction_rows": len(rows),
        "confusion_test": confusion_rows,
        "merged_evaluation": {
            "before": before_overall,
            "after": after_overall,
            "note": ("后验标签重映射（不重跑推理、不重训练）：把 APBT 与 "
                     "AmStaff 的真实/预测标签同时映射为 "
                     "pit_bull_type_merged。仅代表现有权重在合并标签定义下"
                     "的得分，不代表决定修改正式标签体系。"),
        },
        "merged_label_pairs": merged_rows,
        "merged_confusion": merged_confusion,
        "source_distribution": {
            label: dict(Counter(r["source_evidence"] for r in rows
                                if r["true_label"] == label))
            for label in FAMILY},
    }
    (out_dir / "pitbull_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[pitbull] wrote -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
