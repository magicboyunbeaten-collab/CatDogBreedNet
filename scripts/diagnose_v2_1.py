#!/usr/bin/env python
"""V2.1（136 类）误分类诊断：单次推理 + 分桶 + 专项 + 复核材料。

用法（在仓库根目录执行）::

    python scripts/diagnose_v2_1.py

设计：

* **一次推理、多处分桶**。对 ``data/v2_processed/test`` 全量 5,363 张只做一次
  前向，写入 ``all_predictions_136.csv``；后续 136 类报告、原 37 类三桶、专项
  清单、复核队列全部从该表派生，保证各分桶数量可相互核对。
* **稳定样本键**。样本 ID = ``f"{真实类别}/{文件名}"``。已核实
  ``data/processed_clean/test`` 与 ``data/v2_processed/test`` 的 37 个原类文件名
  一一对应，因此 V1.1 与本模型结果按该键对齐，**不依赖 DataLoader 顺序**。
* **置信度口径隔离**。两个模型各自计算 softmax，只用于各自内部统计；
  37 类与 136 类概率空间不同，**不可跨模型比较**。
* 只读 checkpoint 与数据，只写 ``reports/v2_1_diagnostics/``；不改标签、不删图、
  不训练、不回写任何权重。
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
from PIL import Image, ImageDraw, ImageFont
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score, precision_score,
                             recall_score)
from torch.utils.data import DataLoader
from torchvision.datasets import ImageFolder

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ml.dataset import build_transforms  # noqa: E402
from ml.evaluate import save_confusion_matrix  # noqa: E402
from ml.model import load_checkpoint, resolve_device  # noqa: E402

DEFAULT_MODEL_DIR = _REPO_ROOT / "artifacts" / "v2_1_136classes_seed42"
DEFAULT_DATA_DIR = _REPO_ROOT / "data" / "v2_processed"
DEFAULT_V11_WEIGHTS = _REPO_ROOT / "artifacts" / "best_model.pth"
DEFAULT_V11_DATA_DIR = _REPO_ROOT / "data" / "processed_clean"
OUT_DIR = _REPO_ROOT / "reports" / "v2_1_diagnostics"

APBT = "american_pit_bull_terrier"
AMSTAFF = "american_staffordshire_terrier"
SBT = "staffordshire_bull_terrier"
AMBULL = "american_bulldog"
BULLMASTIFF = "bull_mastiff"
PITBULL_FAMILY = (APBT, AMSTAFF, SBT, AMBULL, BULLMASTIFF)
BORDER_FAMILY = ("border_collie", "collie", "border_terrier")

HANDLED_FILENAMES = (
    "all_predictions_136.csv",
    "all_classification_report.csv",
    "confusion_matrix_136.csv",
    "confusion_matrix_136.png",
    "confusion_matrix_136_normalized.png",
    "old37_buckets_summary.csv",
    "old37_predicted_as_new99.csv",
    "original37_v1_vs_v2.csv",
    "apbt_amstaff_predictions.csv",
    "apbt_amstaff_confusion_summary.csv",
    "border_collie_family_predictions.csv",
    "contact_sheet_apbt_amstaff.png",
    "contact_sheet_old37_as_new99.png",
    "diagnostics_summary.json",
)

#: 判断 Stanford（ImageNet synset 命名）与 Oxford 命名。
_STANFORD_RE = re.compile(r"^(n\d{8})_")


def source_evidence(label: str, filename: str) -> str:
    """仅凭文件名给出可复核的来源标识（不猜测、不臆断）。"""
    stem = Path(filename).stem
    match = _STANFORD_RE.match(stem)
    if match:
        return f"Stanford Dogs (ImageNet wnid {match.group(1)})"
    if stem.startswith(label):
        return "Oxford-IIIT Pet"
    return "unknown"


def image_size(path: Path) -> tuple[int, int]:
    try:
        with Image.open(path) as image:
            return image.size
    except Exception:  # noqa: BLE001
        return (0, 0)


def infer_dataset(model, dataset, class_names, device, split,
                  batch_size: int = 32) -> list[dict]:
    """对 ImageFolder 全量推理一次，返回逐图明细（含 top-5 与关键类概率）。"""
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False,
                        num_workers=0)
    # V1.1 只有 37 类、不含 AmStaff；缺失时该列留空，而不是报错中止。
    index_apbt = class_names.index(APBT) if APBT in class_names else None
    index_amstaff = (class_names.index(AMSTAFF)
                     if AMSTAFF in class_names else None)
    rows: list[dict] = []
    cursor = 0
    model.eval()
    with torch.no_grad():
        for images, labels in loader:
            logits = model(images.to(device))
            probs = torch.softmax(logits, dim=1).cpu().numpy()
            for offset, probability in enumerate(probs):
                path_str, _target = dataset.samples[cursor + offset]
                path = Path(path_str)
                label_index = int(labels[offset].item())
                true_label = class_names[label_index]
                order = np.argsort(-probability)
                top_indices = order[:5]
                if index_apbt is None:
                    apbt_prob, apbt_rank = "", ""
                else:
                    apbt_prob = float(probability[index_apbt])
                    apbt_rank = int((probability > apbt_prob).sum()) + 1
                if index_amstaff is None:
                    amstaff_prob, amstaff_rank = "", ""
                else:
                    amstaff_prob = float(probability[index_amstaff])
                    amstaff_rank = int((probability > amstaff_prob).sum()) + 1
                width, height = image_size(path)
                rows.append({
                    "sample_id": f"{true_label}/{path.name}",
                    "split": split,
                    "true_label": true_label,
                    "pred_label": class_names[int(order[0])],
                    "top1_prob": float(probability[order[0]]),
                    "top2_label": class_names[int(order[1])],
                    "top2_prob": float(probability[order[1]]),
                    "top5": "|".join(
                        f"{class_names[int(i)]}:{float(probability[int(i)]):.6f}"
                        for i in top_indices),
                    "apbt_prob": apbt_prob,
                    "apbt_rank": apbt_rank,
                    "amstaff_prob": amstaff_prob,
                    "amstaff_rank": amstaff_rank,
                    "width": width,
                    "height": height,
                    "image_path": str(path),
                    "file_name": path.name,
                    "source_evidence": source_evidence(true_label, path.name),
                })
            cursor += len(labels)
    if cursor != len(dataset.samples):
        raise ValueError(
            f"incomplete inference: {cursor} rows vs {len(dataset.samples)} "
            f"dataset samples")
    return rows


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def make_contact_sheet(items: list[dict], destination: Path, columns: int = 5,
                       cell: int = 200, title: str = "") -> None:
    """生成联系表（只读取原图并缩放，绝不写回原图）。"""
    if not items:
        return
    rows_count = (len(items) + columns - 1) // columns
    header = 40 if title else 0
    sheet = Image.new("RGB", (columns * cell, header + rows_count * (cell + 34)),
                      (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default()
    except Exception:  # noqa: BLE001
        font = None
    if title:
        draw.text((6, 10), title, fill=(0, 0, 0), font=font)
    for index, item in enumerate(items):
        row, col = divmod(index, columns)
        x = col * cell
        y = header + row * (cell + 34)
        try:
            with Image.open(item["image_path"]) as image:
                thumbnail = image.convert("RGB").copy()
            thumbnail.thumbnail((cell - 6, cell - 6))
            sheet.paste(thumbnail, (x + 3, y + 3))
        except Exception:  # noqa: BLE001
            draw.rectangle([x + 3, y + 3, x + cell - 3, y + cell - 3],
                           outline=(200, 0, 0))
        label = (item.get("short_label") or "")[:44]
        draw.text((x + 3, y + cell + 2), label, fill=(0, 0, 0), font=font)
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, quality=85)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--v11-weights", type=Path, default=DEFAULT_V11_WEIGHTS)
    parser.add_argument("--v11-data-dir", type=Path, default=DEFAULT_V11_DATA_DIR)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args(argv)

    out_dir: Path = args.out_dir
    already = [name for name in HANDLED_FILENAMES if (out_dir / name).exists()]
    if already:
        out_dir = out_dir / datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"[diag] target files already exist ({len(already)}); "
              f"writing to {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    device = resolve_device(args.device)
    print(f"[diag] device={device}")

    # ---------------- V2.1 全量推理 ----------------
    model_path = args.model_dir / "best_model.pth"
    classes_path = args.model_dir / "class_names.json"
    model, class_names = load_checkpoint(model_path, device=device)
    saved = json.loads(classes_path.read_text(encoding="utf-8"))
    if list(saved) != list(class_names):
        raise ValueError("class_names.json 与 checkpoint 内类别顺序不一致")
    if len(class_names) != 136:
        raise ValueError(f"期望 136 类，实际 {len(class_names)}")

    test_dir = args.data_dir / "test"
    test_ds = ImageFolder(root=str(test_dir),
                          transform=build_transforms(train=False))
    if list(test_ds.classes) != list(class_names):
        raise ValueError(
            "test 的 ImageFolder 类别顺序与 checkpoint 不一致，停止")
    print(f"[diag] V2.1 test: {len(test_ds.samples)} 张 / "
          f"{len(test_ds.classes)} 类")

    v2_rows = infer_dataset(model, test_ds, class_names, device, split="test")
    write_csv(out_dir / "all_predictions_136.csv", v2_rows,
              ["sample_id", "split", "true_label", "pred_label", "top1_prob",
               "top2_label", "top2_prob", "top5", "apbt_prob", "apbt_rank",
               "amstaff_prob", "amstaff_rank", "width", "height",
               "image_path", "file_name", "source_evidence"])
    print(f"[diag] wrote all_predictions_136.csv ({len(v2_rows)} 行)")

    y_true = [class_names.index(row["true_label"]) for row in v2_rows]
    y_pred = [class_names.index(row["pred_label"]) for row in v2_rows]

    # ---------------- 136 类报告与混淆矩阵 ----------------
    report = classification_report(
        y_true, y_pred, labels=list(range(len(class_names))),
        target_names=class_names, output_dict=True, zero_division=0)
    report_rows = []
    for name in class_names:
        item = report[name]
        report_rows.append({
            "canonical_label": name,
            "precision": round(item["precision"], 6),
            "recall": round(item["recall"], 6),
            "f1": round(item["f1-score"], 6),
            "support": int(item["support"]),
        })
    write_csv(out_dir / "all_classification_report.csv", report_rows,
              ["canonical_label", "precision", "recall", "f1", "support"])

    accuracy = float(accuracy_score(y_true, y_pred))
    macro_f1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_true, y_pred, average="weighted",
                                 zero_division=0))
    matrix = confusion_matrix(y_true, y_pred, labels=list(range(len(class_names))))
    save_confusion_matrix(
        y_true, y_pred, class_names,
        out_dir / "confusion_matrix_136.csv",
        out_dir / "confusion_matrix_136.png",
        out_dir / "confusion_matrix_136_normalized.png",
        split="test")
    print(f"[diag] 136 类: acc={accuracy:.6f} macro_f1={macro_f1:.6f} "
          f"weighted_f1={weighted_f1:.6f}")

    # 与既有 test_metrics.json 交叉核对
    cross_check = {}
    existing_metrics_path = args.model_dir / "test_metrics.json"
    if existing_metrics_path.exists():
        existing = json.loads(existing_metrics_path.read_text(encoding="utf-8"))
        for key, computed in (("accuracy", accuracy),
                              ("macro_f1", macro_f1),
                              ("weighted_f1", weighted_f1)):
            prior = existing.get(key)
            same = (prior is not None
                    and abs(float(prior) - computed) <= 1e-6)
            cross_check[key] = {"existing": prior, "recomputed": computed,
                                "consistent": bool(same)}
            print(f"[diag] 交叉核对 {key}: 既有={prior} 重算={computed:.6f} "
                  f"{'一致' if same else '**不一致**'}")
    else:
        cross_check["note"] = "test_metrics.json 不存在，无法交叉核对"

    # ---------------- 原 37 类三桶分桶 ----------------
    bucket_rows = []
    counts = Counter()
    per_class_bucket: dict[str, Counter] = defaultdict(Counter)
    new_targets = Counter()
    for row in v2_rows:
        if row["true_label"] not in ORIGINAL_37:
            continue
        if row["pred_label"] == row["true_label"]:
            bucket = "correct"
        elif row["pred_label"] in ORIGINAL_37:
            bucket = "to_other_original"
        else:
            bucket = "to_new_99"
            new_targets[row["pred_label"]] += 1
        counts[bucket] += 1
        per_class_bucket[row["true_label"]][bucket] += 1
        bucket_rows.append({**row, "bucket": bucket})

    write_csv(out_dir / "old37_predicted_as_new99.csv",
              [row for row in bucket_rows if row["bucket"] == "to_new_99"],
              ["sample_id", "split", "true_label", "pred_label", "top1_prob",
               "top2_label", "top2_prob", "top5", "image_path",
               "source_evidence", "bucket"])

    bucket_summary = []
    for bucket in ("correct", "to_other_original", "to_new_99"):
        bucket_summary.append({
            "bucket": bucket,
            "count": counts[bucket],
            "ratio": round(counts[bucket] / len(bucket_rows), 6)
            if bucket_rows else 0.0,
        })
    write_csv(out_dir / "old37_buckets_summary.csv", bucket_summary,
              ["bucket", "count", "ratio"])
    print(f"[diag] 原 37 类三桶: {dict(counts)} 合计={len(bucket_rows)}")

    # ---------------- V1.1 同图对比 ----------------
    v11_model, v11_names = load_checkpoint(args.v11_weights, device=device)
    v11_test = ImageFolder(root=str(Path(args.v11_data_dir) / "test"),
                           transform=build_transforms(train=False))
    v11_rows = infer_dataset(v11_model, v11_test, v11_names, device,
                             split="test")
    print(f"[diag] V1.1 test: {len(v11_rows)} 张 / {len(v11_names)} 类")

    v11_by_id = {row["sample_id"]: row for row in v11_rows}
    if len(v11_by_id) != len(v11_rows):
        raise ValueError("V1.1 样本 ID 不唯一")
    v2_by_id = {row["sample_id"]: row for row in bucket_rows}
    missing_in_v11 = sorted(set(v2_by_id) - set(v11_by_id))
    missing_in_v2 = sorted(set(v11_by_id) - set(v2_by_id))
    if missing_in_v11 or missing_in_v2:
        raise ValueError(
            f"样本键匹配失败：V1.1 缺 {len(missing_in_v11)}，"
            f"V2.1 缺 {len(missing_in_v2)}；示例 {missing_in_v11[:3]} "
            f"{missing_in_v2[:3]}")

    compare_rows = []
    for sample_id, v2_row in sorted(v2_by_id.items()):
        v1_row = v11_by_id[sample_id]
        v1_ok = v1_row["pred_label"] == v1_row["true_label"]
        v2_ok = v2_row["pred_label"] == v2_row["true_label"]
        compare_rows.append({
            "sample_id": sample_id,
            "true_label": v2_row["true_label"],
            "v1_pred": v1_row["pred_label"],
            "v1_correct": int(v1_ok),
            "v2_pred": v2_row["pred_label"],
            "v2_correct": int(v2_ok),
            "v2_pred_is_new_breed": int(v2_row["pred_label"] not in ORIGINAL_37),
            "v2_bucket": v2_row["bucket"],
            "v2_top1_prob": round(v2_row["top1_prob"], 6),
            "v1_top1_prob": round(v1_row["top1_prob"], 6),
            "image_path": v2_row["image_path"],
        })
    write_csv(out_dir / "original37_v1_vs_v2.csv", compare_rows,
              ["sample_id", "true_label", "v1_pred", "v1_correct", "v2_pred",
               "v2_correct", "v2_pred_is_new_breed", "v2_bucket",
               "v2_top1_prob", "v1_top1_prob", "image_path"])

    v1_acc = sum(r["v1_correct"] for r in compare_rows) / len(compare_rows)
    v2_acc = sum(r["v2_correct"] for r in compare_rows) / len(compare_rows)
    v1_regressed = sum(1 for r in compare_rows
                       if r["v1_correct"] and not r["v2_correct"])
    v1_improved = sum(1 for r in compare_rows
                      if not r["v1_correct"] and r["v2_correct"])
    print(f"[diag] 同 {len(compare_rows)} 张：V1.1 acc={v1_acc:.4f} "
          f"V2.1 acc={v2_acc:.4f}；V1对→V2错 {v1_regressed}，"
          f"V1错→V2对 {v1_improved}")

    # ---------------- APBT / AmStaff 专项 ----------------
    pitbull_rows = [row for row in v2_rows
                    if row["true_label"] in PITBULL_FAMILY]
    write_csv(out_dir / "apbt_amstaff_predictions.csv", pitbull_rows,
              ["sample_id", "split", "true_label", "pred_label", "top1_prob",
               "top2_label", "top2_prob", "top5", "apbt_prob", "apbt_rank",
               "amstaff_prob", "amstaff_rank", "width", "height",
               "image_path", "file_name", "source_evidence"])

    def confusion_block(label: str, support_expected: int | None) -> dict:
        subset = [row for row in v2_rows if row["true_label"] == label]
        support = len(subset)
        targets = Counter(row["pred_label"] for row in subset)
        correct = targets.get(label, 0)
        probabilities = [row["top1_prob"] for row in subset]
        margins = [row["top1_prob"] - row["top2_prob"] for row in subset]
        # 二值化：y_true = 真实是否为该类；y_pred = 预测是否为该类。
        truth = [1 if r["true_label"] == label else 0 for r in v2_rows]
        called = [1 if r["pred_label"] == label else 0 for r in v2_rows]
        return {
            "true_label": label,
            "support": support,
            "support_expected": support_expected,
            "support_matches_expected": (
                None if support_expected is None else support == support_expected),
            "correct": correct,
            "recall": round(correct / support, 6) if support else 0.0,
            "precision": round(float(precision_score(
                truth, called, zero_division=0)), 6),
            "predicted_count": sum(called),
            "f1": round(float(f1_score(
                truth, called, zero_division=0)), 6),
            "top1_mean": round(float(np.mean(probabilities)), 6)
            if probabilities else 0.0,
            "top1_median": round(float(np.median(probabilities)), 6)
            if probabilities else 0.0,
            "low_confidence_count": sum(1 for p in probabilities if p < 0.5),
            "margin_lt_0_1": sum(1 for m in margins if m < 0.1),
            "top_targets": targets.most_common(),
        }

    apbt_block = confusion_block(APBT, 100)
    amstaff_block = confusion_block(AMSTAFF, 17)
    apbt_as_amstaff = sum(1 for row in v2_rows
                          if row["true_label"] == APBT
                          and row["pred_label"] == AMSTAFF)
    amstaff_as_apbt = sum(1 for row in v2_rows
                          if row["true_label"] == AMSTAFF
                          and row["pred_label"] == APBT)
    sbt_block = confusion_block(SBT, 89)
    ambull_block = confusion_block(AMBULL, 100)
    bullmastiff_block = confusion_block(BULLMASTIFF, 16)

    summary_rows = []
    for block in (apbt_block, amstaff_block, sbt_block, ambull_block,
                  bullmastiff_block):
        summary_rows.append({
            "true_label": block["true_label"],
            "support": block["support"],
            "predicted_count": block["predicted_count"],
            "correct": block["correct"],
            "recall": block["recall"],
            "precision": block["precision"],
            "f1": block["f1"],
            "top1_mean": block["top1_mean"],
            "low_conf_lt_0.5": block["low_confidence_count"],
            "margin_lt_0.1": block["margin_lt_0_1"],
            "top_targets": "; ".join(f"{name}:{count}"
                                     for name, count in block["top_targets"][:6]),
        })
    write_csv(out_dir / "apbt_amstaff_confusion_summary.csv", summary_rows,
              ["true_label", "support", "predicted_count", "correct", "recall",
               "precision", "f1", "top1_mean", "low_conf_lt_0.5",
               "margin_lt_0.1", "top_targets"])

    print(f"[diag] APBT support={apbt_block['support']} "
          f"recall={apbt_block['recall']} -> AmStaff {apbt_as_amstaff}")
    print(f"[diag] AmStaff support={amstaff_block['support']} "
          f"recall={amstaff_block['recall']} -> APBT {amstaff_as_apbt}")

    # 与既有 classification_report.csv 交叉核对（列：class,precision,recall,f1,support）
    blocks = {block["true_label"]: block for block in
              (apbt_block, amstaff_block, sbt_block, ambull_block,
               bullmastiff_block)}
    pitbull_cross: dict[str, dict] = {}
    legacy_report_path = args.model_dir / "classification_report.csv"
    if legacy_report_path.exists():
        legacy: dict[str, dict] = {}
        with legacy_report_path.open(encoding="utf-8") as handle:
            for item in csv.DictReader(handle):
                legacy[item["class"]] = item
        for label, block in blocks.items():
            prior = legacy.get(label)
            if prior is None:
                pitbull_cross[label] = {"present_in_legacy": False}
                continue
            entry = {"present_in_legacy": True, "consistent": {}}
            for key in ("precision", "recall", "f1"):
                prior_value = float(prior[key])
                same = abs(prior_value - block[key]) <= 1e-5
                entry["consistent"][key] = same
                entry[f"{key}_legacy"] = prior_value
                entry[f"{key}_recomputed"] = block[key]
            entry["support_legacy"] = int(float(prior["support"]))
            entry["support_recomputed"] = block["support"]
            entry["consistent"]["support"] = (
                entry["support_legacy"] == entry["support_recomputed"])
            pitbull_cross[label] = entry
            ok_all = all(entry["consistent"].values())
            print(f"[diag] 交叉核对 {label}: 重算 P={block['precision']:.4f} "
                  f"R={block['recall']:.4f} F1={block['f1']:.4f} / "
                  f"既有 P={float(prior['precision']):.4f} "
                  f"R={float(prior['recall']):.4f} "
                  f"F1={float(prior['f1']):.4f} -> "
                  f"{'一致' if ok_all else '**不一致**'}")
    else:
        pitbull_cross["note"] = "classification_report.csv 不存在"

    # ---------------- Border / Collie 专项 ----------------
    border_rows = [row for row in v2_rows
                   if row["true_label"] in BORDER_FAMILY]
    write_csv(out_dir / "border_collie_family_predictions.csv", border_rows,
              ["sample_id", "split", "true_label", "pred_label", "top1_prob",
               "top2_label", "top2_prob", "top5", "width", "height",
               "image_path", "file_name", "source_evidence"])
    border_summary = {}
    for label in BORDER_FAMILY:
        subset = [row for row in v2_rows if row["true_label"] == label]
        targets = Counter(row["pred_label"] for row in subset)
        border_summary[label] = {
            "support": len(subset),
            "correct": targets.get(label, 0),
            "recall": round(targets.get(label, 0) / len(subset), 6)
            if subset else 0.0,
            "top_targets": targets.most_common(5),
        }
        print(f"[diag] {label}: support={len(subset)} "
              f"recall={border_summary[label]['recall']} "
              f"targets={targets.most_common(3)}")

    # ---------------- 联系表 ----------------
    pitbull_cases = [
        {**row, "short_label": f"{row['true_label'][:18]} -> "
                               f"{row['pred_label'][:18]} ({row['top1_prob']:.2f})"}
        for row in v2_rows
        if (row["true_label"] in (APBT, AMSTAFF)
            and row["pred_label"] != row["true_label"])
    ]
    make_contact_sheet(
        pitbull_cases[:40], out_dir / "contact_sheet_apbt_amstaff.png",
        title="APBT / AmStaff 误判样本（真实 -> 预测）")
    print(f"[diag] contact_sheet_apbt_amstaff.png ({len(pitbull_cases[:40])} 例)")

    new99_cases = [
        {**row, "short_label": f"{row['true_label'][:16]} -> "
                               f"{row['pred_label'][:20]} ({row['top1_prob']:.2f})"}
        for row in bucket_rows if row["bucket"] == "to_new_99"
    ]
    new99_cases.sort(key=lambda r: -r["top1_prob"])
    make_contact_sheet(
        new99_cases[:40], out_dir / "contact_sheet_old37_as_new99.png",
        title="原有 37 类被判为新增品种（按置信度降序）")
    print(f"[diag] contact_sheet_old37_as_new99.png "
          f"({len(new99_cases[:40])} 例)")

    # ---------------- 汇总 JSON ----------------
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_dir": str(args.model_dir),
        "data_dir": str(args.data_dir),
        "v11_weights": str(args.v11_weights),
        "v11_data_dir": str(args.v11_data_dir),
        "all_136": {
            "accuracy": accuracy,
            "macro_f1": macro_f1,
            "weighted_f1": weighted_f1,
            "support": len(v2_rows),
            "num_classes": len(class_names),
        },
        "cross_check_with_existing_metrics": cross_check,
        "original_37": {
            "support": len(bucket_rows),
            "buckets": {bucket: counts[bucket] for bucket in
                        ("correct", "to_other_original", "to_new_99")},
            "bucket_rows": bucket_summary,
            "per_class_buckets": {label: dict(counter)
                                  for label, counter in sorted(
                                      per_class_bucket.items())},
            "top_new_targets": new_targets.most_common(15),
        },
        "v1_vs_v2": {
            "matched": len(compare_rows),
            "v1_accuracy": v1_acc,
            "v2_accuracy": v2_acc,
            "v1_correct_v2_wrong": v1_regressed,
            "v1_wrong_v2_correct": v1_improved,
            "v2_predicted_as_new_breed": sum(
                1 for r in compare_rows if r["v2_pred_is_new_breed"]),
        },
        "pitbull_family": {
            block["true_label"]: {
                "support": block["support"],
                "support_expected": block["support_expected"],
                "support_matches_expected": block["support_matches_expected"],
                "correct": block["correct"],
                "predicted_count": block["predicted_count"],
                "recall": block["recall"],
                "precision": block["precision"],
                "f1": block["f1"],
                "top1_mean": block["top1_mean"],
                "top1_median": block["top1_median"],
                "low_confidence_count": block["low_confidence_count"],
                "margin_lt_0_1": block["margin_lt_0_1"],
                "top_targets": block["top_targets"],
            }
            for block in (apbt_block, amstaff_block, sbt_block, ambull_block,
                          bullmastiff_block)
        },
        "pitbull_cross_check": pitbull_cross,
        "bidirectional_confusion": {
            "apbt_to_amstaff": apbt_as_amstaff,
            "apbt_to_amstaff_rate": round(apbt_as_amstaff
                                          / apbt_block["support"], 6)
            if apbt_block["support"] else 0.0,
            "amstaff_to_apbt": amstaff_as_apbt,
            "amstaff_to_apbt_rate": round(amstaff_as_apbt
                                          / amstaff_block["support"], 6)
            if amstaff_block["support"] else 0.0,
        },
        "border_family": border_summary,
        "source_distribution": {
            label: dict(Counter(
                row["source_evidence"] for row in v2_rows
                if row["true_label"] == label))
            for label in PITBULL_FAMILY
        },
    }
    (out_dir / "diagnostics_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[diag] wrote diagnostics_summary.json -> {out_dir}")
    return 0


#: Oxford 原有 37 类的 canonical label（用于三桶分桶）。
ORIGINAL_37 = {
    "Abyssinian", "Bengal", "Birman", "Bombay", "British_Shorthair",
    "Egyptian_Mau", "Maine_Coon", "Persian", "Ragdoll", "Russian_Blue",
    "Siamese", "Sphynx",
    "american_bulldog", "american_pit_bull_terrier", "basset_hound", "beagle",
    "boxer", "chihuahua", "english_cocker_spaniel", "english_setter",
    "german_shorthaired", "great_pyrenees", "havanese", "japanese_chin",
    "keeshond", "leonberger", "miniature_pinscher", "newfoundland",
    "pomeranian", "pug", "saint_bernard", "samoyed", "scottish_terrier",
    "shiba_inu", "staffordshire_bull_terrier", "wheaten_terrier",
    "yorkshire_terrier",
}


if __name__ == "__main__":
    raise SystemExit(main())
