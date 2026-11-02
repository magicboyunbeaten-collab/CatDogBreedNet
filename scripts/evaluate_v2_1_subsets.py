#!/usr/bin/env python
"""V2.1（136 类）子集与分组指标：从混淆矩阵精确重算，不重复推理。

用法（在仓库根目录执行）::

    python scripts/evaluate_v2_1_subsets.py
    python scripts/evaluate_v2_1_subsets.py \
        --model-dir artifacts/v2_1_136classes_seed42

前置：``python -m ml.evaluate --split test`` 已把 ``confusion_matrix.csv`` 与
``test_metrics.json`` 写入 ``--model-dir``，且同一目录有 ``class_names.json``。

为什么从混淆矩阵重算：混淆矩阵已包含全部 true×pred 计数，子集的
Accuracy / Macro-F1 / Weighted-F1 与逐类 P/R/F1 都可精确导出，无需再次
跑 5,363 张图，也避免"为了子集指标再推理一次"带来的口径漂移。

本脚本只读 ``--model-dir`` 内的评估产物与 ``reports/v2_class_catalog.json``，
只写 ``metrics.json`` 与 ``v2_1_subset_metrics.csv``，不碰模型、数据与正式产物。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

#: 12 个原有猫品种（与数据准备阶段保持一致，见
#: ``scripts/build_v2_class_catalog.py`` 的 ``CAT_BREEDS``）。
CAT_BREEDS = (
    "Abyssinian", "Bengal", "Birman", "Bombay", "British_Shorthair",
    "Egyptian_Mau", "Maine_Coon", "Persian", "Ragdoll", "Russian_Blue",
    "Siamese", "Sphynx",
)

#: 需要单独报告的重点类别（任务要求）。
KEY_BREEDS = (
    "border_collie", "collie", "border_terrier",
    "american_staffordshire_terrier", "american_pit_bull_terrier",
    "english_cocker_spaniel", "scottish_terrier",
)

KEY_BREED_NOTES = {
    "border_collie": "边境牧羊犬（新增）",
    "collie": "柯利牧羊犬（新增，与边牧不同品种）",
    "border_terrier": "边境梗（新增，与边牧不同品种）",
    "american_staffordshire_terrier": "AmStaff（新增，独立于 APBT）",
    "american_pit_bull_terrier": "APBT（原有 37 类，未与 AmStaff 合并）",
    "english_cocker_spaniel": "英国可卡犬（原有 37 类；cocker_spaniel 已排除）",
    "scottish_terrier": "苏格兰梗（原有 37 类，别名 Scotch_terrier 已合并）",
}


def load_confusion_matrix(path: Path) -> tuple[np.ndarray, list[str]]:
    """读取 ``true\\pred`` 表头的混淆矩阵 CSV。"""
    with path.open(encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        labels = header[1:]
        rows: list[list[int]] = []
        row_labels: list[str] = []
        for row in reader:
            if not row:
                continue
            row_labels.append(row[0])
            rows.append([int(value) for value in row[1:]])
    matrix = np.asarray(rows, dtype=np.int64)
    if matrix.shape != (len(labels), len(labels)):
        raise ValueError(
            f"confusion matrix is not square: {matrix.shape} vs "
            f"{len(labels)} labels")
    if row_labels != labels:
        raise ValueError(
            "confusion matrix row/column label order differs; refusing to "
            "compute subset metrics")
    return matrix, labels


def per_class_table(matrix: np.ndarray, labels: list[str]) -> list[dict]:
    """由计数矩阵导出每类 support / TP / precision / recall / F1。"""
    support = matrix.sum(axis=1)
    predicted = matrix.sum(axis=0)
    true_positive = np.diag(matrix)
    rows = []
    for index, label in enumerate(labels):
        tp = int(true_positive[index])
        sup = int(support[index])
        pred = int(predicted[index])
        precision = tp / pred if pred else 0.0
        recall = tp / sup if sup else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) else 0.0)
        rows.append({
            "canonical_label": label,
            "support": sup,
            "predicted": pred,
            "true_positive": tp,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        })
    return rows


def subset_metrics(rows: list[dict], indices: list[int],
                   name: str) -> dict:
    """由逐类表计算子集指标（只统计给定类别下标）。"""
    if not indices:
        return {"name": name, "num_classes": 0, "support": 0,
                "accuracy": 0.0, "macro_f1": 0.0, "weighted_f1": 0.0,
                "macro_precision": 0.0, "macro_recall": 0.0}
    selected = [rows[i] for i in indices]
    support = sum(item["support"] for item in selected)
    correct = sum(item["true_positive"] for item in selected)
    macro_f1 = float(np.mean([item["f1"] for item in selected]))
    macro_precision = float(np.mean([item["precision"] for item in selected]))
    macro_recall = float(np.mean([item["recall"] for item in selected]))
    if support:
        weighted_f1 = float(sum(item["f1"] * item["support"]
                                for item in selected) / support)
    else:
        weighted_f1 = 0.0
    return {
        "name": name,
        "num_classes": len(selected),
        "support": support,
        "correct": correct,
        "accuracy": (correct / support) if support else 0.0,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model-dir", type=Path,
                        default=_REPO_ROOT / "artifacts"
                        / "v2_1_136classes_seed42")
    parser.add_argument("--catalog", type=Path,
                        default=_REPO_ROOT / "reports" / "v2_class_catalog.json")
    args = parser.parse_args(argv)

    model_dir: Path = args.model_dir
    matrix_path = model_dir / "confusion_matrix.csv"
    names_path = model_dir / "class_names.json"
    for path in (matrix_path, names_path):
        if not path.exists():
            print(f"[subsets] missing {path}", file=sys.stderr)
            return 1

    matrix, matrix_labels = load_confusion_matrix(matrix_path)
    class_names = json.loads(names_path.read_text(encoding="utf-8"))
    if matrix_labels != class_names:
        print("[subsets] confusion-matrix label order differs from "
              "class_names.json; refusing to continue", file=sys.stderr)
        return 1

    rows = per_class_table(matrix, class_names)
    index_of = {name: i for i, name in enumerate(class_names)}

    # ---- 分组定义（口径来自 v2_class_catalog.json）----------------------
    original_cats = [name for name in CAT_BREEDS if name in index_of]
    original_all = []
    new_breeds = []
    if args.catalog.exists():
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        for entry in catalog["classes"]:
            label = entry["canonical_label"]
            if label not in index_of:
                continue
            if entry["overlaps_existing_37"]:
                original_all.append(label)
            elif (entry["is_new_breed"]
                  and entry["v2_included_from"] != "excluded_ambiguous"):
                new_breeds.append(label)
    else:
        print(f"[subsets] warning: {args.catalog} missing; falling back to "
              f"'all classes that are not in CAT_BREEDS == new breeds'",
              file=sys.stderr)
        original_all = list(original_cats)
        new_breeds = [name for name in class_names
                      if name not in set(original_cats)]

    original_dogs = [name for name in original_all
                     if name not in set(original_cats)]

    groups = [
        ("all_136", list(class_names)),
        ("original_37", original_all),
        ("original_cats_12", original_cats),
        ("original_dogs_25", original_dogs),
        ("new_breeds_99", new_breeds),
    ]

    results = []
    for name, labels in groups:
        indices = [index_of[label] for label in labels if label in index_of]
        metrics = subset_metrics(rows, indices, name)
        results.append(metrics)
        print(f"[subsets] {name:<18} classes={metrics['num_classes']:>3} "
              f"support={metrics['support']:>5} "
              f"acc={metrics['accuracy']:.4f} "
              f"macro_f1={metrics['macro_f1']:.4f} "
              f"weighted_f1={metrics['weighted_f1']:.4f}")

    # ---- 重点类别 --------------------------------------------------------
    key_results = []
    for label in KEY_BREEDS:
        if label not in index_of:
            key_results.append({"canonical_label": label, "present": False,
                                "note": KEY_BREED_NOTES.get(label, "")})
            continue
        item = rows[index_of[label]]
        key_results.append({
            "canonical_label": label,
            "note": KEY_BREED_NOTES.get(label, ""),
            "present": True,
            "support": item["support"],
            "true_positive": item["true_positive"],
            "precision": item["precision"],
            "recall": item["recall"],
            "f1": item["f1"],
        })
    print()
    print("[subsets] 重点类别：")
    for item in key_results:
        if not item.get("present"):
            print(f"  {item['canonical_label']:<32} **不在模型类别中**")
            continue
        print(f"  {item['canonical_label']:<32} n={item['support']:>4} "
              f"P={item['precision']:.4f} R={item['recall']:.4f} "
              f"F1={item['f1']:.4f}")

    # ---- 新增 99 类中最差的 5 类 ----------------------------------------
    new_rows = [rows[index_of[label]] for label in new_breeds
                if label in index_of]
    worst = sorted(new_rows, key=lambda r: r["f1"])[:5]
    print()
    print("[subsets] 新增品种中 F1 最低的 5 类：")
    for item in worst:
        print(f"  {item['canonical_label']:<34} n={item['support']:>4} "
              f"F1={item['f1']:.4f}")

    # ---- 输出 -----------------------------------------------------------
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_dir": str(model_dir),
        "num_classes": len(class_names),
        "evaluated_split": "test",
        "protocol_note": (
            "V2.1 为 136 类模型；V1.1 为 37 类模型，两者类别空间不同，"
            "overall 指标不可当作严格同协议胜负。original_37 子集可作辅助比较，"
            "但预测空间从 37 扩展到 136 后错误去向已改变。"),
        "group_definitions": {
            "all_136": "data/v2_processed 的全部有效类别",
            "original_37": "Oxford 原有 37 类（12 猫 + 25 狗），"
                           "沿用 data/processed_clean 的测试样本",
            "original_cats_12": "原有 12 个猫品种",
            "original_dogs_25": "原有 25 个狗品种",
            "new_breeds_99": "Stanford Dogs 新增且通过审核的 99 个犬种",
        },
        "groups": {item["name"]: item for item in results},
        "key_breeds": key_results,
        "worst_new_breeds": worst,
        "per_class": rows,
    }
    metrics_path = model_dir / "metrics.json"
    metrics_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                            encoding="utf-8")

    csv_path = model_dir / "v2_1_subset_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["group", "num_classes", "support", "correct",
                         "accuracy", "macro_f1", "weighted_f1",
                         "macro_precision", "macro_recall"])
        for item in results:
            writer.writerow([item["name"], item["num_classes"], item["support"],
                             item.get("correct", ""), f"{item['accuracy']:.6f}",
                             f"{item['macro_f1']:.6f}",
                             f"{item['weighted_f1']:.6f}",
                             f"{item['macro_precision']:.6f}",
                             f"{item['macro_recall']:.6f}"])

    print()
    print(f"[subsets] wrote {metrics_path}")
    print(f"[subsets] wrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
