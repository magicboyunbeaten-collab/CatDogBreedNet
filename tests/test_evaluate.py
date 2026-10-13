"""Unit tests for the phase-3 evaluation code.

All tests use synthetic tensors / tiny local models and synthetic JPEGs; they
do not require the real dataset, pretrained weights, or any trained
checkpoint (CODEBUDDY.md section 10.2). Nothing here is a model-accuracy
claim.
"""
import csv
import json
import sys
from pathlib import Path

import pytest
import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, TensorDataset

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.evaluate import (  # noqa: E402
    benchmark_batch_inference,
    benchmark_end_to_end,
    build_summary_markdown,
    collect_predictions,
    compute_metrics,
    save_classification_report_csv,
    save_confusion_matrix,
    save_metrics,
    verify_class_mapping,
)

TOY_CLASSES = ["c0", "c1", "c2"]
# Hand-checkable toy example:
#   class 0: TP=1 FP=1 FN=1 -> P=R=F1=0.5
#   class 1: TP=2 FP=1 FN=0 -> P=2/3 R=1.0 F1=0.8
#   class 2: TP=1 FP=0 FN=1 -> P=1.0 R=0.5 F1=2/3
Y_TRUE = [0, 0, 1, 1, 2, 2]
Y_PRED = [0, 1, 1, 1, 2, 0]


def toy_metrics():
    return compute_metrics(Y_TRUE, Y_PRED, TOY_CLASSES)


# ---------------------------------------------------------------------------
# class mapping verification
# ---------------------------------------------------------------------------

def test_verify_class_mapping_accepts_identical_order():
    verify_class_mapping(["a", "b", "c"], ["a", "b", "c"])  # no raise


def test_verify_class_mapping_rejects_reordered_names():
    with pytest.raises(ValueError, match="class mapping mismatch"):
        verify_class_mapping(["a", "b", "c"], ["a", "c", "b"])


def test_verify_class_mapping_rejects_count_mismatch():
    with pytest.raises(ValueError, match="class count mismatch"):
        verify_class_mapping(["a", "b"], ["a", "b", "c"])


# ---------------------------------------------------------------------------
# metrics correctness
# ---------------------------------------------------------------------------

def test_compute_metrics_accuracy_and_macro_weighted():
    metrics = toy_metrics()
    assert metrics["num_samples"] == 6
    assert metrics["accuracy"] == pytest.approx(4 / 6)
    assert metrics["macro_precision"] == pytest.approx(
        (0.5 + 2 / 3 + 1.0) / 3)
    assert metrics["macro_recall"] == pytest.approx((0.5 + 1.0 + 0.5) / 3)
    assert metrics["macro_f1"] == pytest.approx((0.5 + 0.8 + 2 / 3) / 3)
    assert metrics["weighted_f1"] == pytest.approx(
        (2 * 0.5 + 2 * 0.8 + 2 * (2 / 3)) / 6)
    assert metrics["weighted_recall"] == pytest.approx((0.5 + 1.0 + 0.5) / 3)


def test_compute_metrics_per_class_rows():
    metrics = toy_metrics()
    row = metrics["per_class"]["c1"]
    assert row["precision"] == pytest.approx(2 / 3)
    assert row["recall"] == pytest.approx(1.0)
    assert row["f1"] == pytest.approx(0.8)
    assert row["support"] == 2
    assert metrics["per_class"]["c0"]["support"] == 2


def test_compute_metrics_missing_class_uses_zero_division():
    # class "c1" is never predicted -> precision 0.0 via zero_division=0
    metrics = compute_metrics([0, 0, 1, 1], [0, 0, 0, 0],
                              ["c0", "c1"])
    assert metrics["per_class"]["c1"]["precision"] == 0.0
    assert metrics["per_class"]["c1"]["recall"] == 0.0
    assert metrics["per_class"]["c1"]["support"] == 2
    assert metrics["classes_without_predictions"] == ["c1"]
    assert "zero_division" in metrics["zero_division_policy"]


def test_compute_metrics_reports_no_missing_classes_when_all_predicted():
    metrics = toy_metrics()
    assert metrics["classes_without_predictions"] == []


# ---------------------------------------------------------------------------
# saved products
# ---------------------------------------------------------------------------

def test_saved_products_are_valid(tmp_path):
    metrics = toy_metrics()
    json_path = tmp_path / "test_metrics.json"
    csv_path = tmp_path / "classification_report.csv"
    cm_csv = tmp_path / "confusion_matrix.csv"
    cm_png = tmp_path / "confusion_matrix.png"
    cm_norm_png = tmp_path / "confusion_matrix_normalized.png"

    save_metrics(metrics, json_path)
    save_classification_report_csv(metrics, csv_path)
    cm = save_confusion_matrix(Y_TRUE, Y_PRED, TOY_CLASSES, cm_csv, cm_png,
                               cm_norm_png)

    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded["accuracy"] == pytest.approx(metrics["accuracy"])
    assert loaded["macro_f1"] == pytest.approx(metrics["macro_f1"])

    with csv_path.open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["class", "precision", "recall", "f1", "support"]
    assert [r[0] for r in rows[1:4]] == TOY_CLASSES
    assert rows[4][0] == "accuracy" and rows[5][0] == "macro avg" \
        and rows[6][0] == "weighted avg"

    with cm_csv.open(encoding="utf-8") as fh:
        cm_rows = list(csv.reader(fh))
    assert cm_rows[0] == ["true\\pred"] + TOY_CLASSES
    assert cm_rows[1][0] == "c0"
    assert [int(v) for v in cm_rows[1][1:]] == [1, 1, 0]
    assert [int(v) for v in cm_rows[2][1:]] == [0, 2, 0]
    assert [int(v) for v in cm_rows[3][1:]] == [1, 0, 1]

    assert cm.shape == (3, 3)
    assert cm[0].tolist() == [1, 1, 0]
    assert cm[1].tolist() == [0, 2, 0]
    assert cm[2].tolist() == [1, 0, 1]
    assert cm_png.stat().st_size > 5000
    assert cm_norm_png.stat().st_size > 5000


def test_build_summary_markdown_contains_real_numbers():
    metrics = toy_metrics()
    markdown = build_summary_markdown(
        metrics,
        {"scope": "model_only", "device": "cpu", "gpu": None,
         "cuda_synchronized": False, "batch_size": 4, "warmup_batches": 1,
         "timed_batches": 2, "mean_batch_seconds": 0.01,
         "throughput_images_per_second": 100.0,
         "single_image_latency_ms": {"samples": 8, "mean": 10.0,
                                     "median": 9.0, "p95": 12.0}},
        {"scope": "end_to_end", "device": "cpu", "gpu": None,
         "cuda_synchronized": False, "batch_size": 1, "warmup_images": 1,
         "measured_images": 2,
         "single_image_latency_ms": {"mean": 20.0, "median": 19.0,
                                     "p95": 25.0},
         "throughput_images_per_second": 50.0},
        {"evaluated_at": "2026-10-13T00:00:00+00:00",
         "weights_path": "artifacts/best_model.pth", "dataset": "toy",
         "python": "3.11.9", "torch": "0", "torchvision": "0",
         "gpu": "CPU", "platform": "test"},
        {"指标": Path("reports/test_metrics.json")})
    assert "Macro-F1" in markdown
    assert f"{metrics['macro_f1']:.4f}" in markdown
    assert f"{metrics['accuracy']:.4f}" in markdown
    assert "口径 A" in markdown and "口径 B" in markdown
    assert "不可直接互比" in markdown


# ---------------------------------------------------------------------------
# prediction collection behaviour
# ---------------------------------------------------------------------------

def _toy_model_and_loader(num_classes=3, batch_size=4, samples=6):
    torch.manual_seed(0)
    model = nn.Sequential(nn.Flatten(), nn.Linear(3 * 8 * 8, num_classes))
    images = torch.rand(samples, 3, 8, 8)
    labels = torch.tensor([i % num_classes for i in range(samples)])
    loader = DataLoader(TensorDataset(images, labels), batch_size=batch_size)
    return model, loader


def test_collect_predictions_uses_eval_mode_and_no_grad():
    model, loader = _toy_model_and_loader()
    model.train()  # deliberately start in training mode
    y_true, y_pred = collect_predictions(model, loader, torch.device("cpu"),
                                         expected_total=6)
    assert model.training is False
    assert all(p.grad is None for p in model.parameters())
    assert len(y_true) == 6 and len(y_pred) == 6
    assert set(y_true) == {0, 1, 2}
    assert set(y_pred) <= {0, 1, 2}


def test_collect_predictions_detects_incomplete_evaluation():
    model, loader = _toy_model_and_loader()
    with pytest.raises(ValueError, match="incomplete evaluation"):
        collect_predictions(model, loader, torch.device("cpu"),
                            expected_total=5)


# ---------------------------------------------------------------------------
# benchmarks (CPU smoke tests)
# ---------------------------------------------------------------------------

def test_benchmark_batch_inference_cpu_scope_and_stats():
    model, loader = _toy_model_and_loader(num_classes=4, batch_size=4,
                                          samples=8)
    result = benchmark_batch_inference(model, loader, torch.device("cpu"),
                                       warmup_batches=1, timed_batches=2)
    assert result["scope"] == "model_only_forward_on_test_tensors"
    assert result["includes_preprocessing"] is False
    assert result["measured_images"] == 8
    assert result["throughput_images_per_second"] > 0
    single = result["single_image_latency_ms"]
    assert single["samples"] == 8
    assert single["mean"] >= 0 and single["median"] >= 0
    assert single["p95"] >= single["median"]


def test_benchmark_end_to_end_cpu_includes_preprocessing(tmp_path):
    torch.manual_seed(1)
    model = nn.Sequential(nn.Flatten(), nn.Linear(3 * 224 * 224, 4))
    paths = []
    for i in range(3):
        path = tmp_path / f"img_{i}.jpg"
        Image.new("RGB", (300, 200), (i * 40, 60, 80)).save(path)
        paths.append(path)
    result = benchmark_end_to_end(model, paths, torch.device("cpu"), warmup=1)
    assert result["scope"] == "end_to_end_file_to_prediction"
    assert result["includes_preprocessing"] is True
    assert result["includes_file_io"] is True
    assert result["measured_images"] == 2
    assert result["single_image_latency_ms"]["mean"] > 0
    assert result["throughput_images_per_second"] > 0
