"""Unit tests for the phase-2 model, dataset and prediction code.

All tests use tiny synthetic images and lightweight local models; they do
NOT require the real dataset, pretrained weight downloads, or any trained
checkpoint (CODEBUDDY.md section 10.2). Synthetic results are never used as
model accuracy claims.
"""
import sys
from pathlib import Path

import numpy as np
import pytest
import torch
import torch.nn as nn
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.dataset import (  # noqa: E402
    build_dataloaders,
    build_datasets,
    build_transforms,
    class_names_from_class_to_idx,
)
from ml.model import (  # noqa: E402
    build_model,
    load_checkpoint,
    resolve_device,
    save_checkpoint,
    set_seed,
)
from ml.predict import load_image, predict_from_tensor, predict_image  # noqa: E402

TOY_CLASSES = ["toy_breed_a", "toy_breed_b", "toy_breed_c", "toy_breed_d"]
TOY_IN_FEATURES = 3 * 224 * 224  # matches the 224x224 eval transform output


def toy_model_factory(num_classes: int) -> nn.Module:
    """A minimal model compatible with (N, 3, 224, 224) inputs."""
    return nn.Sequential(nn.Flatten(), nn.Linear(TOY_IN_FEATURES, num_classes))


def make_synthetic_image(path: Path, size=(300, 200), color=(120, 60, 30)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, format="JPEG")


def make_toy_imagefolder(root: Path, classes=("A", "B", "C"), per_class=2) -> None:
    for split in ("train", "val", "test"):
        for ci, cls in enumerate(classes):
            for j in range(per_class):
                make_synthetic_image(
                    root / split / cls / f"{cls.lower()}_{j}.jpg",
                    color=(30 * (ci + 1), 40 * (j + 1), 90))


# ---------------------------------------------------------------------------
# transforms
# ---------------------------------------------------------------------------

def test_eval_transform_output_shape_and_range():
    transform = build_transforms(train=False)
    image = Image.new("RGB", (400, 500), (100, 150, 200))
    tensor = transform(image)
    assert tensor.shape == (3, 224, 224)
    # ImageNet-normalized values must stay in a sane range
    assert tensor.min() > -5 and tensor.max() < 5


def test_train_transform_output_shape():
    transform = build_transforms(train=True)
    image = Image.new("RGB", (400, 500), (10, 20, 30))
    tensor = transform(image)
    assert tensor.shape == (3, 224, 224)


def test_train_transform_is_random():
    transform = build_transforms(train=True)
    image = Image.new("RGB", (400, 500), (80, 80, 80))
    a = transform(image)
    b = transform(image)
    assert not torch.allclose(a, b)  # augmentation introduces randomness


# ---------------------------------------------------------------------------
# dataset
# ---------------------------------------------------------------------------

def test_class_names_from_class_to_idx_orders_by_index():
    names = class_names_from_class_to_idx({"b": 1, "a": 0, "c": 2})
    assert names == ["a", "b", "c"]


def test_build_datasets_consistent_class_mapping(tmp_path):
    make_toy_imagefolder(tmp_path)
    train_ds, val_ds, test_ds = build_datasets(tmp_path)
    assert train_ds.class_to_idx == val_ds.class_to_idx == test_ds.class_to_idx
    assert len(train_ds) == 6 and len(test_ds) == 6


def test_build_dataloaders_batch_shapes(tmp_path):
    make_toy_imagefolder(tmp_path)
    loaders, class_names = build_dataloaders(tmp_path, batch_size=2)
    assert class_names == ["A", "B", "C"]
    images, labels = next(iter(loaders["train"]))
    assert images.shape == (2, 3, 224, 224)
    assert labels.shape == (2,)
    assert set(labels.tolist()) <= set(range(3))


def test_build_datasets_missing_dir_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="missing data directory"):
        build_datasets(tmp_path / "nonexistent")


# ---------------------------------------------------------------------------
# model
# ---------------------------------------------------------------------------

def test_build_model_output_dim_equals_num_classes():
    model = build_model(num_classes=5, pretrained=False)
    out = model(torch.zeros(2, 3, 224, 224))
    assert out.shape == (2, 5)
    assert model.fc.out_features == 5


def test_build_model_rejects_single_class():
    with pytest.raises(ValueError, match="num_classes"):
        build_model(num_classes=1, pretrained=False)


def test_resolve_device_cpu_and_unknown():
    assert resolve_device("cpu").type == "cpu"
    with pytest.raises(ValueError, match="unknown device"):
        resolve_device("bogus")


def test_set_seed_is_deterministic():
    set_seed(123)
    a = torch.rand(3)
    set_seed(123)
    b = torch.rand(3)
    assert torch.equal(a, b)


def test_checkpoint_roundtrip_with_toy_model(tmp_path):
    model = toy_model_factory(len(TOY_CLASSES))
    ckpt = tmp_path / "toy.pth"
    save_checkpoint(model, ckpt, TOY_CLASSES, extra={"epoch": 1},
                    arch="toy_linear")

    loaded, names = load_checkpoint(ckpt, model_factory=toy_model_factory)
    assert names == TOY_CLASSES
    out = loaded(torch.zeros(1, 3, 224, 224))
    assert out.shape == (1, len(TOY_CLASSES))


def test_load_checkpoint_unknown_arch_without_factory_raises(tmp_path):
    model = toy_model_factory(len(TOY_CLASSES))
    ckpt = tmp_path / "toy.pth"
    save_checkpoint(model, ckpt, TOY_CLASSES, arch="toy_linear")
    with pytest.raises(ValueError, match="unsupported checkpoint arch"):
        load_checkpoint(ckpt)


def test_load_checkpoint_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="model weights not found"):
        load_checkpoint(tmp_path / "nope.pth", model_factory=toy_model_factory)


def test_load_checkpoint_class_count_mismatch_raises(tmp_path):
    model = toy_model_factory(len(TOY_CLASSES))
    ckpt = tmp_path / "toy.pth"
    save_checkpoint(model, ckpt, TOY_CLASSES, arch="toy_linear")
    with pytest.raises(ValueError, match="classes"):
        load_checkpoint(ckpt, model_factory=toy_model_factory, num_classes=3)


# ---------------------------------------------------------------------------
# prediction
# ---------------------------------------------------------------------------

def test_predict_from_tensor_topk_and_scores():
    torch.manual_seed(0)
    model = toy_model_factory(len(TOY_CLASSES))
    tensor = torch.rand(3, 224, 224)
    result = predict_from_tensor(model, tensor, TOY_CLASSES, top_k=3, device="cpu")
    assert len(result["predictions"]) == 3
    scores = [p["confidence"] for p in result["predictions"]]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 < s <= 1.0 for s in scores)
    assert result["elapsed_ms"] >= 0
    breeds = [p["breed"] for p in result["predictions"]]
    assert set(breeds) <= set(TOY_CLASSES)


def test_predict_from_tensor_top_k_larger_than_classes_raises():
    model = toy_model_factory(len(TOY_CLASSES))
    with pytest.raises(ValueError, match="top_k"):
        predict_from_tensor(model, torch.rand(3, 224, 224), TOY_CLASSES,
                            top_k=99, device="cpu")


def test_load_image_rejects_non_image(tmp_path):
    bad = tmp_path / "not_an_image.jpg"
    bad.write_text("this is not an image", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot decode"):
        load_image(bad)


def test_predict_image_end_to_end_with_toy_checkpoint(tmp_path):
    torch.manual_seed(7)
    model = toy_model_factory(len(TOY_CLASSES))
    ckpt = tmp_path / "toy.pth"
    save_checkpoint(model, ckpt, TOY_CLASSES, arch="toy_linear")
    image_path = tmp_path / "pet.jpg"
    make_synthetic_image(image_path, color=(200, 100, 50))

    result = predict_image(image_path, top_k=3, weights_path=ckpt,
                           device="cpu", model_factory=toy_model_factory)
    assert result["success"] is True
    assert len(result["predictions"]) == 3
    assert result["num_classes"] == len(TOY_CLASSES)
    assert result["inference_ms"] >= 0
    assert set(p["breed"] for p in result["predictions"]) <= set(TOY_CLASSES)


def test_predict_image_missing_file_raises(tmp_path):
    model = toy_model_factory(len(TOY_CLASSES))
    ckpt = tmp_path / "toy.pth"
    save_checkpoint(model, ckpt, TOY_CLASSES, arch="toy_linear")
    with pytest.raises(FileNotFoundError, match="image not found"):
        predict_image(tmp_path / "missing.jpg", weights_path=ckpt, device="cpu",
                      model_factory=toy_model_factory)
