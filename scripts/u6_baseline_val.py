#!/usr/bin/env python
"""U6-A：用冻结的 V2.1 在 validation 上建立可复现基线（**不训练、不读 test**）。

用法（在仓库根目录执行）::

    # U6-A 基线（tag=val，文件名与计划一致）
    python scripts/u6_baseline_val.py

    # U6-D 候选（复用同一评估代码，保证 split/预处理/指标口径一致）
    python scripts/u6_baseline_val.py --weights artifacts/v2_2_border_collie_exp01_pair_color_jitter_seed42/best_model.pth --tag exp01

产出（写入 ``reports/u6_border_collie/``）：

* ``u6_baseline_{tag}_overall.csv``     136 类 Acc / Macro-F1 / Weighted-F1
* ``u6_baseline_{tag}_groups.csv``      136 / 原 37 / 新增 99 三组
* ``u6_baseline_{tag}_target.csv``      collie 与 border_collie 专项
* ``u6_baseline_{tag}_confusion.csv``   目标相关混淆子矩阵 + 完整 136×136
* ``u6_baseline_{tag}_predictions.csv`` 逐图预测（相对路径 + Top-5）
* ``u6_baseline.json``（仅 tag=val）    V2.1 四文件 SHA256、类别数与顺序校验

**只读**：仅 ``rglob`` ``data/v2_processed/<split>``；脚本内不含 test 路径。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_recall_fscore_support)

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ml.dataset import build_transforms  # noqa: E402
from ml.model import load_checkpoint  # noqa: E402

OUT_DIR = _REPO_ROOT / "reports" / "u6_border_collie"
DATA_DIR = _REPO_ROOT / "data" / "v2_processed"
V21_DIR = _REPO_ROOT / "artifacts" / "v2_1_136classes_seed42"
V11_CLASS_NAMES = _REPO_ROOT / "artifacts" / "class_names.json"

TARGETS = ("collie", "border_collie")
#: 与本任务相关的近似犬种（用于目标相关混淆子矩阵）。
NEIGHBOURS = ("collie", "border_collie", "shetland_sheepdog", "kelpie",
              "groenendael", "cardigan", "pembroke", "old_english_sheepdog",
              "border_terrier")


# ---------------------------------------------------------------------------
# 统计工具
# ---------------------------------------------------------------------------

def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 95% 区间；``total == 0`` 时返回 ``(0, 1)``。"""
    if total <= 0:
        return (0.0, 1.0)
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5) \
        / denominator
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def sha256_file(path: Path) -> str:
    if not path.exists():
        return "<missing>"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def group_metrics(y_true: np.ndarray, y_pred: np.ndarray,
                  indices: list[int], class_names: list[str]) -> dict:
    """在给定类别子集上重算 Acc / Macro-F1 / Weighted-F1。"""
    mask = np.isin(y_true, indices)
    yt, yp = y_true[mask], y_pred[mask]
    if yt.size == 0:
        return {"n": 0, "accuracy": float("nan"),
                "macro_f1": float("nan"), "weighted_f1": float("nan")}
    labels = sorted(set(indices) & set(yt.tolist()) | set(indices))
    return {
        "n": int(yt.size),
        "accuracy": float(accuracy_score(yt, yp)),
        "macro_f1": float(f1_score(yt, yp, labels=labels, average="macro",
                                   zero_division=0)),
        "weighted_f1": float(f1_score(yt, yp, labels=labels,
                                      average="weighted", zero_division=0)),
    }


def class_report_row(y_true: np.ndarray, y_pred: np.ndarray, index: int,
                     class_names: list[str]) -> dict:
    """单个类别的 P/R/F1 + support + Wilson 区间。"""
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=[index], average=None, zero_division=0)
    tp = int(((y_true == index) & (y_pred == index)).sum())
    low, high = wilson_interval(tp, int(support[0]))
    return {
        "class": class_names[index],
        "support": int(support[0]),
        "true_positive": tp,
        "precision": float(precision[0]),
        "recall": float(recall[0]),
        "f1": float(f1[0]),
        "recall_wilson_low": round(low, 4),
        "recall_wilson_high": round(high, 4),
    }


# ---------------------------------------------------------------------------
# 评估主体（供 U6-A 与 U6-D 共用）
# ---------------------------------------------------------------------------

def evaluate_split(weights_path: Path, class_names_path: Path,
                   split: str = "val", batch_size: int = 32,
                   device: str | None = None,
                   image_size: int = 224) -> dict:
    """在指定 split 上推理一次，返回逐图预测与全部指标。

    ``split`` 只接受 ``train`` / ``val``（本任务不使用 test）。
    """
    if split not in ("train", "val"):
        raise ValueError(f"U6 only evaluates train/val, got {split!r}")
    split_dir = DATA_DIR / split
    if not split_dir.is_dir():
        raise FileNotFoundError(f"split directory missing: {split_dir}")

    saved_names = json.loads(Path(class_names_path).read_text(encoding="utf-8"))
    device_obj = torch.device(
        device or ("cuda" if torch.cuda.is_available() else "cpu"))
    model, ckpt_names = load_checkpoint(Path(weights_path), device=device_obj)
    if list(ckpt_names) != list(saved_names):
        raise ValueError(
            f"class mapping mismatch: checkpoint has {len(ckpt_names)} classes, "
            f"{class_names_path} has {len(saved_names)}; refusing to evaluate.")
    class_names = list(ckpt_names)
    index_of = {name: i for i, name in enumerate(class_names)}

    model.eval()
    # 必须与训练时的分辨率一致，否则会人为压低指标（exp04 为 256）。
    transform = build_transforms(train=False, image_size=image_size)

    samples: list[tuple[Path, int]] = []
    for name in class_names:
        class_dir = split_dir / name
        if not class_dir.is_dir():
            raise FileNotFoundError(f"missing class directory: {class_dir}")
        for image_path in sorted(class_dir.glob("*.jpg")):
            samples.append((image_path, index_of[name]))

    from PIL import Image

    rows: list[dict] = []
    probs_all = np.zeros((len(samples), len(class_names)), dtype=np.float32)
    started = time.perf_counter()
    with torch.inference_mode():
        for start in range(0, len(samples), batch_size):
            batch = samples[start:start + batch_size]
            tensors = []
            for image_path, _ in batch:
                with Image.open(image_path) as image:
                    tensors.append(transform(image.convert("RGB")))
            logits = model(torch.stack(tensors).to(device_obj))
            probs = torch.softmax(logits, dim=1).cpu().numpy()
            probs_all[start:start + len(batch)] = probs
    elapsed = time.perf_counter() - started

    for i, (image_path, true_index) in enumerate(samples):
        prob = probs_all[i]
        top5 = np.argsort(-prob)[:5]
        rows.append({
            "image_path": image_path.relative_to(DATA_DIR).as_posix(),
            "true_label": class_names[true_index],
            "true_index": true_index,
            "pred_label": class_names[int(top5[0])],
            "pred_index": int(top5[0]),
            "top1_probability": round(float(prob[top5[0]]), 8),
            "top5": ";".join(f"{class_names[int(j)]}:{prob[j]:.6f}" for j in top5),
        })

    y_true = np.array([r["true_index"] for r in rows], dtype=np.int64)
    y_pred = np.array([r["pred_index"] for r in rows], dtype=np.int64)

    return {
        "split": split,
        "weights_path": str(weights_path),
        "class_names": class_names,
        "class_names_path": str(class_names_path),
        "samples": rows,
        "y_true": y_true,
        "y_pred": y_pred,
        "probs": probs_all,
        "elapsed_seconds": round(elapsed, 2),
        "batch_size": batch_size,
        "device": str(device_obj),
        "confusion": confusion_matrix(y_true, y_pred,
                                     labels=list(range(len(class_names)))),
    }


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = fieldnames or list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def target_analysis(result: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """返回 (target_rows, confusion_rows, full_confusion_rows)。"""
    class_names = result["class_names"]
    y_true, y_pred = result["y_true"], result["y_pred"]
    index_of = {name: i for i, name in enumerate(class_names)}

    target_rows: list[dict] = []
    for name in TARGETS:
        idx = index_of[name]
        row = class_report_row(y_true, y_pred, idx, class_names)
        # 错判去向 Top-5
        wrong = y_pred[(y_true == idx) & (y_pred != idx)]
        destinations = []
        if wrong.size:
            values, counts = np.unique(wrong, return_counts=True)
            order = np.argsort(-counts)[:5]
            destinations = [(class_names[int(values[k])], int(counts[k]))
                            for k in order]
        row["top_error_destinations"] = "; ".join(
            f"{label}:{count}" for label, count in destinations) or "(无)"
        target_rows.append(row)

    collie_i = index_of["collie"]
    border_i = index_of["border_collie"]
    c2b = int(((y_true == collie_i) & (y_pred == border_i)).sum())
    b2c = int(((y_true == border_i) & (y_pred == collie_i)).sum())
    c_total = int((y_true == collie_i).sum())
    b_total = int((y_true == border_i).sum())
    target_rows.append({
        "class": "BIDIRECTIONAL",
        "support": c_total + b_total,
        "true_positive": c_total - c2b + b_total - b2c,
        "precision": float("nan"),
        "recall": float("nan"),
        "f1": float("nan"),
        "recall_wilson_low": "",
        "recall_wilson_high": "",
        "top_error_destinations":
            f"collie->border_collie {c2b}/{c_total}; "
            f"border_collie->collie {b2c}/{b_total}; "
            f"合计 {c2b + b2c}/{(c_total + b_total)}",
    })

    # 目标相关混淆子矩阵
    neighbours = [n for n in NEIGHBOURS if n in index_of]
    confusion = result["confusion"]
    confusion_rows = []
    for true_name in neighbours:
        ti = index_of[true_name]
        row = {"true_label": true_name}
        for pred_name in neighbours:
            row[pred_name] = int(confusion[ti, index_of[pred_name]])
        row["row_total"] = int(confusion[ti].sum())
        row["correct"] = int(confusion[ti, ti])
        confusion_rows.append(row)

    full_rows = []
    for true_name, ti in index_of.items():
        row = {"true_label": true_name}
        for pred_name, pi in index_of.items():
            value = int(confusion[ti, pi])
            if value:
                row[pred_name] = value
        row["row_total"] = int(confusion[ti].sum())
        full_rows.append(row)

    return target_rows, confusion_rows, full_rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--weights", type=Path,
                        default=V21_DIR / "best_model.pth")
    parser.add_argument("--class-names", type=Path,
                        default=V21_DIR / "class_names.json")
    parser.add_argument("--split", default="val", choices=["train", "val"])
    parser.add_argument("--tag", default="val",
                        help="文件名后缀；基线用 val，候选用 exp01 等")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--image-size", type=int, default=224,
                        help="must match the model's training resolution "
                             "(exp04 uses 256)")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = args.tag

    print(f"[u6] weights = {args.weights}")
    print(f"[u6] class_names = {args.class_names}")
    result = evaluate_split(args.weights, args.class_names,
                            split=args.split, batch_size=args.batch_size,
                            image_size=args.image_size)
    class_names = result["class_names"]
    y_true, y_pred = result["y_true"], result["y_pred"]
    print(f"[u6] split={args.split} samples={len(result['samples'])} "
          f"classes={len(class_names)} device={result['device']} "
          f"elapsed={result['elapsed_seconds']}s")

    # ---- overall ----
    labels = list(range(len(class_names)))
    overall = {
        "split": args.split,
        "tag": tag,
        "weights": str(args.weights),
        "class_names": str(args.class_names),
        "n_samples": len(result["samples"]),
        "n_classes": len(class_names),
        "batch_size": result["batch_size"],
        "image_size": args.image_size,
        "device": result["device"],
        "elapsed_seconds": result["elapsed_seconds"],
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        "macro_f1": round(float(f1_score(y_true, y_pred, labels=labels,
                                         average="macro", zero_division=0)), 6),
        "weighted_f1": round(float(f1_score(y_true, y_pred, labels=labels,
                                            average="weighted",
                                            zero_division=0)), 6),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "test_split_access_count": 0,
    }
    write_csv(out_dir / f"u6_baseline_{tag}_overall.csv", [overall])

    # ---- groups ----
    v11_names = json.loads(V11_CLASS_NAMES.read_text(encoding="utf-8"))
    index_of = {name: i for i, name in enumerate(class_names)}
    v11_indices = [index_of[n] for n in v11_names if n in index_of]
    new_indices = [i for i in labels if i not in set(v11_indices)]
    all_indices = labels
    group_rows = []
    for name, subset in (("all_136", all_indices),
                         ("original_37", v11_indices),
                         ("new_99", new_indices)):
        metrics = group_metrics(y_true, y_pred, subset, class_names)
        metrics.update({"group": name, "tag": tag, "split": args.split,
                        "class_count": len(subset)})
        group_rows.append(metrics)
    write_csv(out_dir / f"u6_baseline_{tag}_groups.csv", group_rows)

    # ---- target ----
    target_rows, confusion_rows, full_rows = target_analysis(result)
    for row in target_rows:
        row["tag"] = tag
        row["split"] = args.split
    write_csv(out_dir / f"u6_baseline_{tag}_target.csv", target_rows)
    write_csv(out_dir / f"u6_baseline_{tag}_confusion.csv", confusion_rows)
    # 完整混淆矩阵按"非零列"稀疏存储，各行列集合不同，需先求并集。
    full_fields: list[str] = ["true_label"]
    for row in full_rows:
        for key in row:
            if key not in full_fields:
                full_fields.append(key)
    write_csv(out_dir / f"u6_baseline_{tag}_confusion_full.csv",
              full_rows, full_fields)

    # ---- predictions ----
    write_csv(out_dir / f"u6_baseline_{tag}_predictions.csv",
              result["samples"],
              ["image_path", "true_label", "pred_label",
               "top1_probability", "top5", "true_index", "pred_index"])

    # ---- baseline metadata（仅基线）----
    if tag == "val":
        ckpt_names = list(class_names)
        # 与 ml/train.py 写 experiment_config.json 的口径保持一致，
        # 否则跨脚本比对会得到无意义的"不一致"。
        order_sha = hashlib.sha256(
            json.dumps(ckpt_names).encode("utf-8")).hexdigest()
        config_path = args.weights.parent / "experiment_config.json"
        config_sha = ""
        expected_order_sha = None
        if config_path.exists():
            config = json.loads(config_path.read_text(encoding="utf-8"))
            expected_order_sha = config.get("class_order_sha256")
            config_sha = sha256_file(config_path)
        meta = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model_dir": str(args.weights.parent),
            "num_classes": len(ckpt_names),
            "class_names_equal_json": ckpt_names == json.loads(
                Path(args.class_names).read_text(encoding="utf-8")),
            "class_order_sha256": order_sha,
            "class_order_sha256_matches_config": (
                order_sha == expected_order_sha
                if expected_order_sha else None),
            "files": {
                "best_model.pth": sha256_file(args.weights),
                "class_names.json": sha256_file(args.class_names),
                "model_version.json": sha256_file(
                    args.weights.parent / "model_version.json"),
                "experiment_config.json": config_sha or "<missing>",
            },
            "val_samples": len(result["samples"]),
            "evaluation_command": (
                "python scripts/u6_baseline_val.py "
                f"--weights {args.weights} --class-names {args.class_names} "
                f"--split {args.split} --tag {tag}"),
            "test_split_access_count": 0,
            "note": ("U6-A 基线：只用 validation。test 在前序任务中已被查看过"
                     "汇总指标与错分案例，不能视为未接触的盲测集。"),
        }
        (out_dir / "u6_baseline.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[u6] class_order_sha256 = {order_sha}")
        print(f"[u6] matches experiment_config = "
              f"{meta['class_order_sha256_matches_config']}")

    print(f"[u6] overall: acc={overall['accuracy']:.6f} "
          f"macroF1={overall['macro_f1']:.6f} "
          f"weightedF1={overall['weighted_f1']:.6f}")
    for row in group_rows:
        print(f"[u6] group {row['group']:<12} n={row['n']:<6} "
              f"acc={row['accuracy']:.6f} macroF1={row['macro_f1']:.6f}")
    for row in target_rows:
        if row["class"] == "BIDIRECTIONAL":
            print(f"[u6] 双向混滑: {row['top_error_destinations']}")
        else:
            print(f"[u6] {row['class']:<16} support={row['support']:<4} "
                  f"P={row['precision']:.4f} R={row['recall']:.4f} "
                  f"F1={row['f1']:.4f}")
    print(f"[u6] wrote outputs with tag={tag} to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
