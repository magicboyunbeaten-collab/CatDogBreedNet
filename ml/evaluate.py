#!/usr/bin/env python
"""Evaluate the trained model on a chosen dataset split.

Usage (from the repository root):

    python -m ml.evaluate                       # full test-set evaluation + benchmark
    python -m ml.evaluate --no-benchmark        # metrics only
    python -m ml.evaluate --timed-batches 100   # longer inference benchmark
    python -m ml.evaluate --split val           # validation-split metrics
                                                   (for model/strategy selection
                                                   without touching the test split)

The test split is the official Oxford-IIIT test split (3669 images) and was
never used for training or model selection. This script only *measures* the
already-selected best checkpoint; it never re-trains or re-selects models.

``--split`` defaults to ``test`` so the default behaviour is unchanged; ``val``
and ``train`` exist so a checkpoint can be scored on the validation split
(e.g. to report validation Macro-F1 for strategy selection) without ever
reading the test split.

Products (written to reports/):
    test_metrics.json           accuracy, macro/weighted P-R-F1, per-class rows
    classification_report.csv   per-class precision/recall/f1/support
    confusion_matrix.csv        raw 37x37 counts with class names
    confusion_matrix.png        annotated counts heatmap
    confusion_matrix_normalized.png  row-normalized heatmap
    inference_benchmark.json    warm-up + CUDA-synced timing, two scopes
    evaluation_summary.md       human-readable summary of everything above
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Allow running as a plain script: python ml/evaluate.py
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import numpy as np  # noqa: E402
import torch  # noqa: E402
import torchvision  # noqa: E402

# 服务端评估脚本不需要 GUI：显式使用无头后端，避免 matplotlib 试图加载
# TkAgg 而报 `_tkinter.TclError: Can't find a usable tk.tcl`（曾导致测试偶发失败）。
import matplotlib  # noqa: E402

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402
from PIL import Image  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from ml.config import (  # noqa: E402
    PROCESSED_DATA_DIR,
    REPORTS_DIR,
    SEED,
    VAL_RATIO,
)
from ml.dataset import build_dataloaders, build_transforms  # noqa: E402
from ml.model import (  # noqa: E402
    BEST_WEIGHTS_PATH,
    CLASS_NAMES_PATH,
    EXPERIMENT_CONFIG_PATH,
    load_checkpoint,
    load_class_names,
    resolve_device,
    verify_class_mapping,
)

__all__ = [
    "benchmark_batch_inference",
    "benchmark_end_to_end",
    "build_summary_markdown",
    "collect_predictions",
    "compute_metrics",
    "save_classification_report_csv",
    "save_confusion_matrix",
    "save_metrics",
    "verify_class_mapping",
]


# ---------------------------------------------------------------------------
# Prediction collection
# ---------------------------------------------------------------------------

def collect_predictions(model, loader, device, expected_total=None,
                        progress_every=0):
    """Run inference over *loader* once and return (y_true, y_pred).

    The model is switched to eval mode and wrapped in ``torch.no_grad()``.
    Every sample is evaluated exactly once. When ``expected_total`` is given,
    a mismatch between the number of predictions and the dataset size raises
    ``ValueError`` (guards against silently partial evaluations).
    """
    model.eval()
    y_true: list[int] = []
    y_pred: list[int] = []
    with torch.no_grad():
        for batch_idx, (images, labels) in enumerate(loader):
            logits = model(images.to(device))
            predictions = logits.argmax(dim=1).tolist()
            y_pred.extend(predictions)
            y_true.extend(labels.tolist())
            if progress_every and (batch_idx + 1) % progress_every == 0:
                print(f"[evaluate] {batch_idx + 1}/{len(loader)} batches, "
                      f"{len(y_true)} images", flush=True)
    if expected_total is not None and len(y_true) != expected_total:
        raise ValueError(
            f"incomplete evaluation: collected {len(y_true)} predictions but "
            f"expected {expected_total} (dataset size).")
    return y_true, y_pred


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(y_true, y_pred, class_names) -> dict:
    """Compute accuracy, macro/weighted P-R-F1 and per-class metrics.

    Classes without any predicted sample get precision 0.0 via
    ``zero_division=0``; they are also listed explicitly in
    ``classes_without_predictions`` so the report can explain the artifact.
    """
    labels = list(range(len(class_names)))
    report = classification_report(
        y_true, y_pred, labels=labels, target_names=class_names,
        output_dict=True, zero_division=0)
    per_class = {
        name: {
            "precision": report[name]["precision"],
            "recall": report[name]["recall"],
            "f1": report[name]["f1-score"],
            "support": int(report[name]["support"]),
        }
        for name in class_names
    }
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    no_prediction = [name for name, col in zip(class_names, cm.T)
                     if col.sum() == 0]

    return {
        "num_samples": len(y_true),
        "num_classes": len(class_names),
        "accuracy": accuracy_score(y_true, y_pred),
        "macro_precision": precision_score(
            y_true, y_pred, labels=labels, average="macro", zero_division=0),
        "macro_recall": recall_score(
            y_true, y_pred, labels=labels, average="macro", zero_division=0),
        "macro_f1": f1_score(
            y_true, y_pred, labels=labels, average="macro", zero_division=0),
        "weighted_precision": precision_score(
            y_true, y_pred, labels=labels, average="weighted",
            zero_division=0),
        "weighted_recall": recall_score(
            y_true, y_pred, labels=labels, average="weighted",
            zero_division=0),
        "weighted_f1": f1_score(
            y_true, y_pred, labels=labels, average="weighted",
            zero_division=0),
        "per_class": per_class,
        "classes_without_predictions": no_prediction,
        "zero_division_policy": (
            "classes with no predicted samples receive precision=0.0 "
            "(sklearn zero_division=0); recall and f1 remain defined by the "
            "ground-truth support"),
    }


def save_metrics(metrics: dict, json_path: Path) -> None:
    json_path = Path(json_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")


def save_classification_report_csv(metrics: dict, csv_path: Path) -> None:
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["class", "precision", "recall", "f1", "support"])
        for name, row in metrics["per_class"].items():
            writer.writerow([name, f"{row['precision']:.6f}",
                             f"{row['recall']:.6f}", f"{row['f1']:.6f}",
                             row["support"]])
        writer.writerow(["accuracy", "", "", f"{metrics['accuracy']:.6f}",
                         metrics["num_samples"]])
        writer.writerow(["macro avg", f"{metrics['macro_precision']:.6f}",
                         f"{metrics['macro_recall']:.6f}",
                         f"{metrics['macro_f1']:.6f}", ""])
        writer.writerow(["weighted avg", f"{metrics['weighted_precision']:.6f}",
                         f"{metrics['weighted_recall']:.6f}",
                         f"{metrics['weighted_f1']:.6f}", ""])


def save_confusion_matrix(y_true, y_pred, class_names, csv_path: Path,
                          png_path: Path, normalized_png_path: Path | None = None,
                          split: str = "test"):
    """Save the raw confusion matrix as CSV and annotated heatmaps as PNG."""
    labels = list(range(len(class_names)))
    cm = confusion_matrix(y_true, y_pred, labels=labels)

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["true\\pred"] + class_names)
        for name, row in zip(class_names, cm):
            writer.writerow([name] + [int(v) for v in row])

    _plot_confusion_matrix(cm, class_names, png_path, normalize=False,
                           split=split)
    if normalized_png_path is not None:
        _plot_confusion_matrix(cm, class_names, normalized_png_path,
                               normalize=True, split=split)
    return cm


def confusion_matrix_title(normalize: bool, split: str, total: int,
                           n: int) -> str:
    """混淆矩阵图标题（抽成独立函数以便直接测试 split 口径）。"""
    base = ("Confusion matrix (row-normalized)" if normalize
            else "Confusion matrix (counts)")
    return f"{base} - {split} split, {total} images, {n} breeds"


def _plot_confusion_matrix(cm, class_names, png_path: Path,
                           normalize: bool, split: str = "test") -> None:
    matrix = cm.astype(float)
    if normalize:
        row_sums = matrix.sum(axis=1, keepdims=True)
        matrix = np.divide(matrix, row_sums, out=np.zeros_like(matrix),
                           where=row_sums != 0)
    n = len(class_names)
    fig, ax = plt.subplots(figsize=(max(10, 0.46 * n + 3), max(9, 0.46 * n + 2)))
    im = ax.imshow(matrix, cmap="Blues",
                   interpolation="nearest",
                   vmin=0, vmax=(None if normalize else matrix.max()))
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ticks = np.arange(n)
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels(class_names, rotation=90, fontsize=max(6, 160 // n))
    ax.set_yticklabels(class_names, fontsize=max(6, 160 // n))
    ax.set_xlabel("predicted breed")
    ax.set_ylabel("true breed")
    ax.set_title(confusion_matrix_title(normalize, split, int(cm.sum()), n))

    threshold = (matrix.max() / 2) if matrix.max() > 0 else 0.5
    for i in range(n):
        for j in range(n):
            value = matrix[i, j]
            if value == 0:
                continue
            text = f"{value:.2f}" if normalize else f"{int(value)}"
            ax.text(j, i, text, ha="center", va="center",
                    fontsize=max(5, 150 // n),
                    color="white" if value > threshold else "black")
    fig.tight_layout()
    png_path = Path(png_path)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Inference benchmarks (two clearly separated scopes)
# ---------------------------------------------------------------------------

def _synchronize(device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return float("nan")
    return float(np.percentile(np.asarray(values, dtype=float), pct))


def benchmark_batch_inference(model, loader, device, warmup_batches: int = 10,
                              timed_batches: int = 50,
                              split: str = "test") -> dict:
    """Model-only timing on real split tensors (no file IO, no preprocessing).

    CUDA events are synchronized around every timed region; the first
    ``warmup_batches`` batches are discarded so CUDA initialization and
    autotuning do not pollute the measurements. ``split`` only labels the
    reported scope; the timing itself is identical for any split.
    """
    model.eval()
    batches: list[torch.Tensor] = []
    iterator = iter(loader)

    def next_batch() -> torch.Tensor:
        nonlocal iterator
        try:
            images, _ = next(iterator)
        except StopIteration:
            iterator = iter(loader)
            images, _ = next(iterator)
        return images

    with torch.no_grad():
        for _ in range(warmup_batches):
            model(next_batch().to(device))
        _synchronize(device)

        batch_seconds: list[float] = []
        single_seconds: list[float] = []
        for _ in range(timed_batches):
            images = next_batch()
            _synchronize(device)
            started = time.perf_counter()
            model(images.to(device))
            _synchronize(device)
            batch_seconds.append(time.perf_counter() - started)
            # Single-image latency: time each image of this batch separately.
            for image in images:
                _synchronize(device)
                t0 = time.perf_counter()
                model(image.unsqueeze(0).to(device))
                _synchronize(device)
                single_seconds.append(time.perf_counter() - t0)

    batch_size = loader.batch_size
    total_images = int(batch_size * timed_batches)
    mean_batch = statistics.mean(batch_seconds)
    return {
        "scope": f"model_only_forward_on_{split}_tensors",
        "includes_preprocessing": False,
        "includes_file_io": False,
        "device": str(device),
        "gpu": (torch.cuda.get_device_name(device)
                if device.type == "cuda" else None),
        "cuda_synchronized": device.type == "cuda",
        "batch_size": batch_size,
        "warmup_batches": warmup_batches,
        "timed_batches": timed_batches,
        "measured_images": total_images,
        "mean_batch_seconds": mean_batch,
        "median_batch_seconds": statistics.median(batch_seconds),
        "p95_batch_seconds": _percentile(batch_seconds, 95),
        "throughput_images_per_second": total_images / sum(batch_seconds),
        "single_image_latency_ms": {
            "samples": len(single_seconds),
            "mean": statistics.mean(single_seconds) * 1000,
            "median": statistics.median(single_seconds) * 1000,
            "p95": _percentile(single_seconds, 95) * 1000,
        },
    }


def benchmark_end_to_end(model, image_paths, device, warmup: int = 5) -> dict:
    """File-to-prediction timing: disk read + PIL decode + transform + forward.

    Clearly separated from the model-only benchmark above; both numbers are
    reported and must not be compared directly.
    """
    transform = build_transforms(train=False)
    model.eval()
    latencies_ms: list[float] = []

    with torch.no_grad():
        for path in image_paths[:warmup]:
            with Image.open(path) as im:
                tensor = transform(im.convert("RGB"))
            model(tensor.unsqueeze(0).to(device))
        _synchronize(device)

        for path in image_paths[warmup:]:
            _synchronize(device)
            started = time.perf_counter()
            with Image.open(path) as im:
                tensor = transform(im.convert("RGB"))
            logits = model(tensor.unsqueeze(0).to(device))
            _synchronize(device)
            latencies_ms.append((time.perf_counter() - started) * 1000)

    return {
        "scope": "end_to_end_file_to_prediction",
        "includes_preprocessing": True,
        "includes_file_io": True,
        "device": str(device),
        "gpu": (torch.cuda.get_device_name(device)
                if device.type == "cuda" else None),
        "cuda_synchronized": device.type == "cuda",
        "batch_size": 1,
        "warmup_images": warmup,
        "measured_images": len(latencies_ms),
        "single_image_latency_ms": {
            "samples": len(latencies_ms),
            "mean": statistics.mean(latencies_ms) if latencies_ms else None,
            "median": statistics.median(latencies_ms) if latencies_ms else None,
            "p95": _percentile(latencies_ms, 95) if latencies_ms else None,
        },
        "throughput_images_per_second": (
            len(latencies_ms) / (sum(latencies_ms) / 1000)
            if latencies_ms else None),
    }


def _collect_test_image_paths(test_dataset, count: int) -> list[Path]:
    paths = [Path(sample[0]) for sample in test_dataset.samples[:count]]
    return paths


# ---------------------------------------------------------------------------
# Summary document
# ---------------------------------------------------------------------------

def build_summary_markdown(metrics: dict, batch_bench: dict, e2e_bench: dict,
                           env: dict, product_paths: dict) -> str:
    lines: list[str] = []
    split = env.get("split", "test")
    split_zh = {"test": "测试集", "val": "验证集", "train": "训练集"}.get(
        split, split)
    lines.append(f"# {split_zh}评估报告（split={split}）")
    lines.append("")
    lines.append(f"- 评估时间：{env['evaluated_at']}")
    lines.append(f"- 权重文件：`{env['weights_path']}`")
    if split == "test":
        lines.append("- 口径：官方 test 划分，**未**用于训练或模型选择；"
                     "阶段 2 按验证集选模")
    elif split == "val":
        lines.append("- 口径：**验证集**指标，用于模型/策略选择；"
                     "与最终测试集指标必须分开解读")
    else:
        lines.append("- 口径：**训练集**指标，仅反映拟合程度，"
                     "**不能**用于衡量泛化能力")
    lines.append(f"- 数据集：{env['dataset']}，`{split}` 划分 "
                 f"{metrics['num_samples']} 张，{metrics['num_classes']} 类")
    lines.append(f"- 环境：{env['python']} / torch {env['torch']} / "
                 f"torchvision {env['torchvision']} / {env['gpu']} / "
                 f"{env['platform']}")
    lines.append("")
    lines.append("## 总体指标（真实推理结果）")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|---|---|")
    lines.append(f"| Top-1 Accuracy | {metrics['accuracy']:.4f} |")
    lines.append(f"| Macro Precision | {metrics['macro_precision']:.4f} |")
    lines.append(f"| Macro Recall | {metrics['macro_recall']:.4f} |")
    lines.append(f"| **Macro-F1** | **{metrics['macro_f1']:.4f}** |")
    lines.append(f"| Weighted Precision | {metrics['weighted_precision']:.4f} |")
    lines.append(f"| Weighted Recall | {metrics['weighted_recall']:.4f} |")
    lines.append(f"| **Weighted-F1** | **{metrics['weighted_f1']:.4f}** |")
    lines.append("")
    lines.append(f"测试样本总数：**{metrics['num_samples']}**（与数据集大小一致，"
                 f"每张图片只评估一次）。")
    lines.append("")

    best = sorted(metrics["per_class"].items(),
                  key=lambda kv: kv[1]["f1"], reverse=True)
    lines.append("## 表现最好的品种（按 F1）")
    lines.append("")
    lines.append("| 品种 | Precision | Recall | F1 | Support |")
    lines.append("|---|---|---|---|---|")
    for name, row in best[:5]:
        lines.append(f"| {name} | {row['precision']:.4f} | "
                     f"{row['recall']:.4f} | {row['f1']:.4f} | "
                     f"{row['support']} |")
    lines.append("")
    lines.append("## 表现最弱的品种（按 F1）")
    lines.append("")
    lines.append("| 品种 | Precision | Recall | F1 | Support |")
    lines.append("|---|---|---|---|---|")
    for name, row in best[-5:]:
        lines.append(f"| {name} | {row['precision']:.4f} | "
                     f"{row['recall']:.4f} | {row['f1']:.4f} | "
                     f"{row['support']} |")
    lines.append("")

    if metrics["classes_without_predictions"]:
        lines.append("## 无预测样本的类别")
        lines.append("")
        lines.append("以下类别在整个测试集中没有被预测过，其 Precision 按 "
                     "`zero_division=0` 记为 0.0（Recall/F1 仍由真实支持数"
                     "决定）：")
        lines.append("")
        for name in metrics["classes_without_predictions"]:
            lines.append(f"- {name}")
    else:
        lines.append("## 无预测样本的类别")
        lines.append("")
        lines.append(f"无——{metrics['num_classes']} 个类别在该划分中都至少被"
                     f"预测过一次，`zero_division=0` 未实际生效。")
    lines.append("")

    if batch_bench and e2e_bench:
        lines.append("## 推理性能（两个计时口径，不可直接互比）")
        lines.append("")
        lines.append(f"### 口径 A：模型纯推理（{batch_bench['scope']}）")
        lines.append("")
        lines.append(f"- 设备：{batch_bench['device']}"
                     f"{'（' + batch_bench['gpu'] + '）' if batch_bench['gpu'] else ''}")
        lines.append(f"- batch size：{batch_bench['batch_size']}；"
                     f"预热 {batch_bench['warmup_batches']} 个 batch；"
                     f"计时 {batch_bench['timed_batches']} 个 batch；"
                     f"CUDA 同步：{batch_bench['cuda_synchronized']}")
        lines.append(f"- 平均单 batch 时间："
                     f"{batch_bench['mean_batch_seconds'] * 1000:.2f} ms")
        lines.append(f"- 批处理吞吐："
                     f"{batch_bench['throughput_images_per_second']:.1f} images/s")
        single = batch_bench["single_image_latency_ms"]
        lines.append(f"- 单张延迟（batch=1 单独前向，{single['samples']} 次）："
                     f"平均 {single['mean']:.2f} ms / 中位数 "
                     f"{single['median']:.2f} ms / P95 {single['p95']:.2f} ms")
        lines.append("")
        lines.append(f"### 口径 B：端到端（{e2e_bench['scope']}）")
        lines.append("")
        lines.append(f"- 包含图片文件读取、PIL 解码、预处理与模型前向；"
                     f"batch size：{e2e_bench['batch_size']}；"
                     f"预热 {e2e_bench['warmup_images']} 张；"
                     f"计时 {e2e_bench['measured_images']} 张；"
                     f"CUDA 同步：{e2e_bench['cuda_synchronized']}")
        e2e_single = e2e_bench["single_image_latency_ms"]
        lines.append(f"- 单张延迟：平均 {e2e_single['mean']:.2f} ms / 中位数 "
                     f"{e2e_single['median']:.2f} ms / P95 {e2e_single['p95']:.2f} ms")
        lines.append(f"- 吞吐：{e2e_bench['throughput_images_per_second']:.1f} "
                     f"images/s")
        lines.append("")
    else:
        # --no-benchmark：跳过计时章节（此前会因空 dict 取 ['scope'] 而崩溃）
        lines.append("## 推理性能")
        lines.append("")
        lines.append("- 本次以 `--no-benchmark` 运行，未做推理计时；"
                     "上方指标仍为真实推理结果。")
        lines.append("")
    lines.append("## 产物文件")
    lines.append("")
    for label, path in product_paths.items():
        lines.append(f"- {label}：`{path}`")
    lines.append("")
    lines.append("## 已知限制")
    lines.append("")
    if split == "test":
        lines.append("- 以上指标仅反映该权重在官方 test 划分上的表现；"
                     "test 划分未用于训练或模型选择；")
    else:
        lines.append(f"- 以上指标仅反映该权重在 **{split_zh}（split={split}）**"
                     f"划分上的表现；该划分**不能**替代官方 test 集的最终评估；")
    lines.append("- Softmax 分数是当前类别集合上的归一化分数，不是真实概率；")
    lines.append("- 不保证识别训练类别之外的动物、物体或无效图片。")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the trained model on the held-out test set.")
    parser.add_argument("--weights", type=Path, default=BEST_WEIGHTS_PATH)
    parser.add_argument("--class-names", type=Path, default=CLASS_NAMES_PATH,
                        help="optional cross-check file for the class order")
    parser.add_argument("--data-dir", type=Path, default=PROCESSED_DATA_DIR)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--device", default="auto",
                        choices=["auto", "cpu", "cuda"])
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--split", default="test",
                        choices=["test", "val", "train"],
                        help="which split to evaluate; defaults to 'test' so "
                             "the default behaviour is unchanged. Use 'val' "
                             "to score a checkpoint on the validation split "
                             "(e.g. to report validation Macro-F1 for model "
                             "selection without touching the test split).")
    parser.add_argument("--no-benchmark", action="store_true",
                        help="skip the inference benchmark")
    parser.add_argument("--warmup-batches", type=int, default=10)
    parser.add_argument("--timed-batches", type=int, default=50)
    parser.add_argument("--e2e-images", type=int, default=100,
                        help="number of real test images for the end-to-end "
                             "benchmark (plus warmup)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    device = resolve_device(args.device)

    model, checkpoint_class_names = load_checkpoint(args.weights, device=device)
    if args.class_names.exists():
        saved_class_names = load_class_names(args.class_names)
        verify_class_mapping(checkpoint_class_names, saved_class_names)
        print(f"[evaluate] class_names.json matches the checkpoint "
              f"({len(saved_class_names)} classes)")

    loaders, dataset_class_names = build_dataloaders(
        processed_dir=args.data_dir, batch_size=args.batch_size,
        num_workers=args.num_workers)
    if args.split not in loaders:
        raise ValueError(
            f"split '{args.split}' not found in {args.data_dir}; "
            f"available: {sorted(loaders)}")
    eval_loader = loaders[args.split]
    verify_class_mapping(checkpoint_class_names, dataset_class_names)
    num_classes = len(dataset_class_names)
    expected_total = len(eval_loader.dataset)
    print(f"[evaluate] device={device} split={args.split} "
          f"images={expected_total} classes={num_classes}")

    started = time.time()
    y_true, y_pred = collect_predictions(
        model, eval_loader, device, expected_total=expected_total,
        progress_every=20)
    metrics = compute_metrics(y_true, y_pred, dataset_class_names)
    metrics["weights_path"] = str(args.weights)
    metrics["data_dir"] = str(args.data_dir)
    metrics["split"] = args.split
    metrics["split_policy"] = (
        f"split='{args.split}' of {args.data_dir}. For split='test' this is "
        "the official test split, never used for training or model selection "
        f"(seed={SEED}, val_ratio={VAL_RATIO} for train/val). For split='val' "
        "these are validation-split metrics used for model/strategy "
        "selection; for split='train' they are training-split metrics and "
        "say nothing about generalisation.")
    metrics["evaluated_at"] = datetime.now(timezone.utc).isoformat()
    metrics["evaluation_seconds"] = round(time.time() - started, 2)
    print(f"[evaluate] done: {metrics['num_samples']} images in "
          f"{metrics['evaluation_seconds']}s; "
          f"accuracy={metrics['accuracy']:.4f} "
          f"macro_f1={metrics['macro_f1']:.4f} "
          f"weighted_f1={metrics['weighted_f1']:.4f}")

    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = reports_dir / "test_metrics.json"
    report_csv_path = reports_dir / "classification_report.csv"
    cm_csv_path = reports_dir / "confusion_matrix.csv"
    cm_png_path = reports_dir / "confusion_matrix.png"
    cm_norm_png_path = reports_dir / "confusion_matrix_normalized.png"
    benchmark_path = reports_dir / "inference_benchmark.json"
    summary_path = reports_dir / "evaluation_summary.md"

    save_metrics(metrics, metrics_path)
    save_classification_report_csv(metrics, report_csv_path)
    save_confusion_matrix(y_true, y_pred, dataset_class_names, cm_csv_path,
                          cm_png_path, cm_norm_png_path, split=args.split)
    print(f"[evaluate] saved {metrics_path.name}, {report_csv_path.name}, "
          f"{cm_csv_path.name}, {cm_png_path.name}, "
          f"{cm_norm_png_path.name}")

    benchmark = {
        "evaluated_at": metrics["evaluated_at"],
        "weights_path": str(args.weights),
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "torchvision": torchvision.__version__,
            "cuda_available": torch.cuda.is_available(),
            "gpu": (torch.cuda.get_device_name(device)
                    if device.type == "cuda" else None),
            "platform": platform.platform(),
        },
        "model_only_batch_benchmark": None,
        "end_to_end_benchmark": None,
    }
    if not args.no_benchmark:
        batch_bench = benchmark_batch_inference(
            model, eval_loader, device,
            warmup_batches=args.warmup_batches,
            timed_batches=args.timed_batches, split=args.split)
        image_paths = _collect_test_image_paths(
            eval_loader.dataset, args.e2e_images + 5)
        e2e_bench = benchmark_end_to_end(
            model, image_paths, device, warmup=5)
        benchmark["model_only_batch_benchmark"] = batch_bench
        benchmark["end_to_end_benchmark"] = e2e_bench
        benchmark_path.write_text(
            json.dumps(benchmark, indent=2, ensure_ascii=False),
            encoding="utf-8")
        print(f"[evaluate] benchmark: batch throughput "
              f"{batch_bench['throughput_images_per_second']:.1f} img/s, "
              f"single-image mean "
              f"{batch_bench['single_image_latency_ms']['mean']:.2f} ms, "
              f"end-to-end mean "
              f"{e2e_bench['single_image_latency_ms']['mean']:.2f} ms")
    else:
        benchmark_path.write_text(
            json.dumps(benchmark, indent=2, ensure_ascii=False),
            encoding="utf-8")

    env = {
        "evaluated_at": metrics["evaluated_at"],
        "weights_path": str(args.weights),
        "dataset": f"Oxford-IIIT Pet Dataset ({args.data_dir})",
        "split": args.split,
        "python": platform.python_version(),
        "torch": torch.__version__,
        "torchvision": torchvision.__version__,
        "gpu": (torch.cuda.get_device_name(device)
                if device.type == "cuda" else "CPU"),
        "platform": platform.platform(),
    }
    product_paths = {
        "总体指标 JSON": metrics_path,
        "逐类别分类报告 CSV": report_csv_path,
        "混淆矩阵 CSV": cm_csv_path,
        "混淆矩阵图（计数）": cm_png_path,
        "混淆矩阵图（行归一化）": cm_norm_png_path,
        "推理性能 JSON": benchmark_path,
        "实验配置（阶段 2）": EXPERIMENT_CONFIG_PATH,
    }
    summary_path.write_text(
        build_summary_markdown(
            metrics,
            benchmark.get("model_only_batch_benchmark") or {},
            benchmark.get("end_to_end_benchmark") or {},
            env, product_paths),
        encoding="utf-8")
    print(f"[evaluate] saved {summary_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
