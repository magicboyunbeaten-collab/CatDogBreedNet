"""Tests for the V1.1 training-pipeline extensions (A2/A3/A4 experiments).

Covers the backward-compatible additions to the training pipeline:
multi-architecture ``build_model``, augmentation presets, freeze strategies,
per-group learning rates and Mixup. Everything runs on CPU with
``pretrained=False`` so no network access or checkpoint is required.
Nothing here is a model-accuracy claim (CODEBUDDY.md section 10.2).
"""
import sys
from pathlib import Path

import pytest
import torch
import torch.nn as nn

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.dataset import AUGMENT_PRESETS, build_transforms  # noqa: E402
from ml.model import SUPPORTED_ARCHS, build_model  # noqa: E402
from ml.train import (  # noqa: E402
    AUGMENT_DESCRIPTIONS,
    apply_freeze_strategy,
    build_optimizer,
    train_one_epoch,
)

ALL_ARCHS = ["resnet18", "resnet50", "convnext_tiny", "efficientnet_b0"]


def _kinds(compose):
    return [type(step).__name__ for step in compose.transforms]


# ---------------------------------------------------------------------------
# A4: 多架构
# ---------------------------------------------------------------------------

def test_supported_archs_contains_baseline_and_candidates():
    assert set(ALL_ARCHS) <= set(SUPPORTED_ARCHS)
    # 基线必须是受支持架构之一（默认值）
    assert "resnet18" in SUPPORTED_ARCHS


def test_build_model_default_arch_is_resnet18():
    default = build_model(num_classes=4, pretrained=False)
    assert isinstance(default.fc, nn.Linear)
    assert default.fc.out_features == 4
    explicit = build_model(arch="resnet18", num_classes=4, pretrained=False)
    assert type(default) is type(explicit)


@pytest.mark.parametrize("arch", ALL_ARCHS)
def test_build_model_each_arch_produces_num_classes_logits(arch):
    model = build_model(arch=arch, num_classes=3, pretrained=False)
    model.eval()
    with torch.no_grad():
        out = model(torch.zeros(1, 3, 224, 224))
    assert out.shape == (1, 3)


def test_build_model_rejects_unknown_arch():
    with pytest.raises(ValueError, match="unsupported arch"):
        build_model(arch="mobilenet_v3", num_classes=3, pretrained=False)


def test_build_model_rejects_single_class():
    with pytest.raises(ValueError, match="num_classes"):
        build_model(num_classes=1, pretrained=False)


@pytest.mark.parametrize("arch", ["resnet50", "convnext_tiny",
                                  "efficientnet_b0"])
def test_save_checkpoint_records_arch_and_round_trips(tmp_path, arch):
    """Regression: 非默认架构必须把 arch 写入 checkpoint。

    ``save_checkpoint`` 的 ``arch`` 默认值是基线的 resnet18；若训练时忘记
    显式传入，checkpoint 会被误标成 resnet18，``load_checkpoint`` 随即用错误
    架构加载并报形状不匹配（A4_resnet50 评估失败的真实原因）。
    """
    from ml.model import load_checkpoint, save_checkpoint

    class_names = ["a", "b", "c"]
    model = build_model(arch=arch, num_classes=3, pretrained=False)
    path = tmp_path / "model.pth"
    save_checkpoint(model, path, class_names, arch=arch)

    payload = torch.load(path, map_location="cpu", weights_only=False)
    assert payload["arch"] == arch

    loaded, loaded_names = load_checkpoint(path, device=torch.device("cpu"))
    assert loaded_names == class_names
    loaded.eval()
    with torch.no_grad():
        assert loaded(torch.zeros(1, 3, 224, 224)).shape == (1, 3)


# ---------------------------------------------------------------------------
# A2: 增强预设
# ---------------------------------------------------------------------------

def test_baseline_augment_matches_stage2_pipeline():
    kinds = _kinds(build_transforms(train=True, augment="baseline"))
    assert kinds == ["RandomResizedCrop", "RandomHorizontalFlip",
                     "RandomRotation", "ToTensor", "Normalize"]


def test_colorjitter_preset_prepends_jitter():
    kinds = _kinds(build_transforms(train=True, augment="+colorjitter"))
    assert kinds[0] == "ColorJitter"
    assert kinds[-2:] == ["ToTensor", "Normalize"]
    assert "RandomResizedCrop" in kinds


def test_randomerasing_preset_appends_after_totensor():
    kinds = _kinds(build_transforms(train=True, augment="+randomerasing"))
    assert "RandomErasing" in kinds
    assert kinds.index("RandomErasing") > kinds.index("ToTensor")
    assert kinds[-1] == "RandomErasing"


def test_eval_transform_ignores_augment():
    """评估/推理管线必须保持确定性，与 augment 无关。"""
    base = _kinds(build_transforms(train=False, augment="baseline"))
    assert base == ["Resize", "CenterCrop", "ToTensor", "Normalize"]
    for preset in AUGMENT_PRESETS:
        assert _kinds(build_transforms(train=False, augment=preset)) == base


def test_build_transforms_rejects_unknown_preset():
    with pytest.raises(ValueError, match="augment preset"):
        build_transforms(train=True, augment="+cutmix")


def test_augment_descriptions_cover_every_preset():
    assert set(AUGMENT_DESCRIPTIONS) == set(AUGMENT_PRESETS)


# ---------------------------------------------------------------------------
# A3: 冻结策略与分层学习率
# ---------------------------------------------------------------------------

def test_freeze_none_trains_every_parameter():
    model = build_model(num_classes=3, pretrained=False)
    description = apply_freeze_strategy(model, "resnet18", "none")
    assert all(p.requires_grad for p in model.parameters())
    assert "all parameters trainable" in description


def test_freeze_head_only_trains_classifier():
    model = build_model(num_classes=3, pretrained=False)
    description = apply_freeze_strategy(model, "resnet18", "head")
    assert all(p.requires_grad for p in model.fc.parameters())
    assert not any(p.requires_grad for p in model.layer4.parameters())
    assert not any(p.requires_grad for p in model.conv1.parameters())
    assert "fc" in description


def test_freeze_layer4_trains_last_stage_and_head():
    model = build_model(num_classes=3, pretrained=False)
    description = apply_freeze_strategy(model, "resnet18", "layer4")
    assert all(p.requires_grad for p in model.layer4.parameters())
    assert all(p.requires_grad for p in model.fc.parameters())
    assert not any(p.requires_grad for p in model.layer3.parameters())
    assert "layer4" in description


def test_freeze_layer4_on_convnext_uses_last_feature_block():
    model = build_model(arch="convnext_tiny", num_classes=3, pretrained=False)
    description = apply_freeze_strategy(model, "convnext_tiny", "layer4")
    assert all(p.requires_grad for p in model.classifier.parameters())
    last_block = list(model.features.children())[-1]
    assert all(p.requires_grad for p in last_block.parameters())
    assert "features[-1]" in description


def test_freeze_strategy_rejects_unknown_value():
    model = build_model(num_classes=3, pretrained=False)
    with pytest.raises(ValueError, match="freeze strategy"):
        apply_freeze_strategy(model, "resnet18", "everything")


def test_optimizer_default_is_single_group():
    model = build_model(num_classes=3, pretrained=False)
    optimizer = build_optimizer(model, "resnet18", lr=1e-3,
                                weight_decay=1e-4)
    assert len(optimizer.param_groups) == 1
    assert optimizer.param_groups[0]["lr"] == pytest.approx(1e-3)


def test_optimizer_per_group_learning_rates():
    model = build_model(num_classes=3, pretrained=False)
    optimizer = build_optimizer(model, "resnet18", lr=1e-3,
                                weight_decay=1e-4,
                                lr_head=1e-3, lr_backbone=1e-4)
    lrs = {g["name"]: g["lr"] for g in optimizer.param_groups}
    assert lrs["head"] == pytest.approx(1e-3)
    assert lrs["backbone"] == pytest.approx(1e-4)


def test_optimizer_skips_frozen_backbone_group():
    model = build_model(num_classes=3, pretrained=False)
    apply_freeze_strategy(model, "resnet18", "head")
    optimizer = build_optimizer(model, "resnet18", lr=1e-3,
                                weight_decay=1e-4,
                                lr_head=1e-3, lr_backbone=1e-4)
    head_group = next(g for g in optimizer.param_groups if g["name"] == "head")
    assert len(head_group["params"]) == len(list(model.fc.parameters()))
    assert not any(g["name"] == "backbone" for g in optimizer.param_groups)


# ---------------------------------------------------------------------------
# A2d: Mixup
# ---------------------------------------------------------------------------

def _toy_loader():
    torch.manual_seed(0)
    images = torch.rand(4, 3, 224, 224)
    labels = torch.tensor([0, 1, 2, 0])
    return [(images, labels)]


def test_train_one_epoch_without_mixup_returns_finite_metrics():
    model = build_model(num_classes=3, pretrained=False)
    criterion = nn.CrossEntropyLoss()
    optimizer = build_optimizer(model, "resnet18", lr=1e-3, weight_decay=0.0)
    loss, accuracy = train_one_epoch(
        model, _toy_loader(), criterion, optimizer, torch.device("cpu"))
    assert loss > 0 and loss == loss
    assert 0.0 <= accuracy <= 1.0


def test_train_one_epoch_with_mixup_returns_finite_metrics():
    model = build_model(num_classes=3, pretrained=False)
    criterion = nn.CrossEntropyLoss()
    optimizer = build_optimizer(model, "resnet18", lr=1e-3, weight_decay=0.0)
    loss, accuracy = train_one_epoch(
        model, _toy_loader(), criterion, optimizer, torch.device("cpu"),
        mixup_alpha=0.2)
    assert loss > 0 and loss == loss
    assert 0.0 <= accuracy <= 1.0
