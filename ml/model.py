"""Model construction and checkpoint utilities.

The baseline is torchvision's ResNet18 with ImageNet pretrained weights and
a replaced fully-connected head producing ``num_classes`` logits.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Callable, NamedTuple

import numpy as np
import torch
import torch.nn as nn
from torchvision import models

from ml.config import ARTIFACTS_DIR

BEST_WEIGHTS_PATH = ARTIFACTS_DIR / "best_model.pth"
LAST_WEIGHTS_PATH = ARTIFACTS_DIR / "last_model.pth"
CLASS_NAMES_PATH = ARTIFACTS_DIR / "class_names.json"
EXPERIMENT_CONFIG_PATH = ARTIFACTS_DIR / "experiment_config.json"

ARCH = "resnet18"
PRETRAINED_WEIGHTS = "IMAGENET1K_V1"


class _ArchSpec(NamedTuple):
    """How to build one supported backbone and swap its classification head."""

    factory: Callable[..., nn.Module]
    weights: object  # torchvision weights enum, or None when not pretrained
    head_in_features: Callable[[nn.Module], int]
    set_head: Callable[[nn.Module, int], None]


def _set_fc_head(model: nn.Module, num_classes: int) -> None:
    """Replace a ResNet-style ``fc`` linear head."""
    model.fc = nn.Linear(model.fc.in_features, num_classes)


def _last_linear_in_features(sequential: nn.Sequential) -> int:
    """Return ``in_features`` of the final ``nn.Linear`` in a Sequential."""
    for module in reversed(sequential):
        if isinstance(module, nn.Linear):
            return module.in_features
    raise ValueError("classifier Sequential contains no nn.Linear")


def _set_sequential_head(model: nn.Module, num_classes: int) -> None:
    """Replace the final linear of a ConvNeXt/EfficientNet-style classifier."""
    classifier = model.classifier
    if not isinstance(classifier, nn.Sequential):
        raise ValueError("expected a Sequential classifier")
    indices = [i for i, m in enumerate(classifier) if isinstance(m, nn.Linear)]
    if not indices:
        raise ValueError("classifier Sequential contains no nn.Linear")
    idx = indices[-1]
    classifier[idx] = nn.Linear(classifier[idx].in_features, num_classes)


#: Architectures available for the A4 backbone comparison experiment.
#: ``resnet18`` is the baseline and the default for every existing caller.
SUPPORTED_ARCHS: dict[str, _ArchSpec] = {
    "resnet18": _ArchSpec(
        factory=models.resnet18,
        weights=models.ResNet18_Weights.IMAGENET1K_V1,
        head_in_features=lambda m: m.fc.in_features,
        set_head=_set_fc_head,
    ),
    "resnet50": _ArchSpec(
        factory=models.resnet50,
        weights=models.ResNet50_Weights.IMAGENET1K_V1,
        head_in_features=lambda m: m.fc.in_features,
        set_head=_set_fc_head,
    ),
    "convnext_tiny": _ArchSpec(
        factory=models.convnext_tiny,
        weights=models.ConvNeXt_Tiny_Weights.IMAGENET1K_V1,
        head_in_features=lambda m: _last_linear_in_features(m.classifier),
        set_head=_set_sequential_head,
    ),
    "efficientnet_b0": _ArchSpec(
        factory=models.efficientnet_b0,
        weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1,
        head_in_features=lambda m: _last_linear_in_features(m.classifier),
        set_head=_set_sequential_head,
    ),
}


def set_seed(seed: int = 42) -> None:
    """Fix random seeds for reproducibility (random/numpy/torch/cuda)."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def resolve_device(device: str = "auto") -> torch.device:
    """Resolve 'auto'/'cpu'/'cuda' to a torch.device with clear errors."""
    if device == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError(
                "device 'cuda' requested but torch.cuda.is_available() is "
                "False. Check the NVIDIA driver / CUDA build of PyTorch, or "
                "use --device cpu.")
        return torch.device("cuda")
    if device == "cpu":
        return torch.device("cpu")
    raise ValueError(f"unknown device '{device}'; expected auto|cpu|cuda")


def build_model(arch: str = ARCH, num_classes: int = 37,
                pretrained: bool = True) -> nn.Module:
    """Build a backbone with an ``num_classes``-way classification head.

    ``arch`` must be a key of :data:`SUPPORTED_ARCHS`; it defaults to
    ``"resnet18"`` so every existing caller keeps the baseline behaviour.

    Raises ``ValueError`` for unknown architectures or ``num_classes < 2``,
    and ``RuntimeError`` if the pretrained weights cannot be obtained
    (e.g. download failure) -- we never silently fall back to random
    initialization (CODEBUDDY.md 6.4).
    """
    if arch not in SUPPORTED_ARCHS:
        raise ValueError(
            f"unsupported arch '{arch}'; expected one of {sorted(SUPPORTED_ARCHS)}")
    if num_classes < 2:
        raise ValueError(f"num_classes must be >= 2, got {num_classes}")
    spec = SUPPORTED_ARCHS[arch]
    try:
        weights = spec.weights if pretrained else None
        model = spec.factory(weights=weights)
    except Exception as exc:  # download / hub errors surface here
        raise RuntimeError(
            f"failed to obtain pretrained {arch} weights "
            f"({type(exc).__name__}: {exc}). "
            "Check network access to download.pytorch.org and that TORCH_HOME "
            "points to a writable directory. Refusing to fall back to random "
            "weights silently.") from exc
    spec.set_head(model, num_classes)
    return model


def save_checkpoint(
    model: nn.Module,
    path: Path,
    class_names: list[str],
    extra: dict | None = None,
    arch: str = ARCH,
) -> None:
    """Save model weights plus metadata (arch, class names, class count)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "arch": arch,
        "num_classes": len(class_names),
        "class_names": list(class_names),
        "state_dict": model.state_dict(),
    }
    if extra:
        payload.update(extra)
    torch.save(payload, path)


def _default_factory(arch: str):
    """Return the default model factory for a checkpoint architecture."""
    if arch not in SUPPORTED_ARCHS:
        raise ValueError(
            f"unsupported checkpoint arch '{arch}'; pass an explicit "
            f"model_factory(num_classes) to load_checkpoint().")
    return lambda num_classes: build_model(arch, num_classes, pretrained=False)


def load_checkpoint(
    path: Path = BEST_WEIGHTS_PATH,
    model_factory=None,
    device: torch.device | str | None = None,
    num_classes: int | None = None,
) -> tuple[nn.Module, list[str]]:
    """Load a checkpoint saved by :func:`save_checkpoint`.

    ``model_factory`` maps ``num_classes -> nn.Module`` and defaults to
    ResNet18 with a random head (weights come from the checkpoint anyway).
    Validates file existence, payload structure and class-count consistency
    before returning ``(model, class_names)``.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"model weights not found: {path}. Train a model first with "
            f"'python -m ml.train'.")

    try:
        payload = torch.load(path, map_location="cpu", weights_only=True)
    except Exception:
        payload = torch.load(path, map_location="cpu", weights_only=False)

    for key in ("state_dict", "class_names", "num_classes"):
        if key not in payload:
            raise ValueError(f"checkpoint {path} is missing key '{key}'")
    class_names = list(payload["class_names"])
    saved_classes = int(payload["num_classes"])
    if saved_classes != len(class_names):
        raise ValueError(
            f"checkpoint {path}: num_classes={saved_classes} but "
            f"{len(class_names)} class names stored")
    if num_classes is not None and num_classes != saved_classes:
        raise ValueError(
            f"checkpoint {path} stores {saved_classes} classes but "
            f"{num_classes} were requested")

    factory = model_factory or _default_factory(payload.get("arch", ARCH))
    model = factory(saved_classes)
    model.load_state_dict(payload["state_dict"])  # strict=True
    if device is None:
        device = "cpu"
    model.to(torch.device(device)).eval()
    return model, class_names


def save_class_names(class_names: list[str], path: Path = CLASS_NAMES_PATH) -> None:
    """Persist the ordered class list as JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(class_names), indent=2, ensure_ascii=False),
                    encoding="utf-8")


def load_class_names(path: Path = CLASS_NAMES_PATH) -> list[str]:
    """Load the ordered class list written by :func:`save_class_names`."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"class names file not found: {path}")
    return list(json.loads(path.read_text(encoding="utf-8")))


def verify_class_mapping(model_class_names, dataset_class_names) -> None:
    """Fail loudly when two label mappings differ.

    The order matters: index i of the model output must correspond to the
    same breed in the dataset, otherwise predictions would be mislabeled.
    """
    model_names = list(model_class_names)
    dataset_names = list(dataset_class_names)
    if len(model_names) != len(dataset_names):
        raise ValueError(
            f"class count mismatch: checkpoint has {len(model_names)} classes "
            f"but the dataset has {len(dataset_names)}. Retrain or rebuild the "
            f"dataset so both agree.")
    for idx, (a, b) in enumerate(zip(model_names, dataset_names)):
        if a != b:
            raise ValueError(
                f"class mapping mismatch at index {idx}: checkpoint='{a}' "
                f"dataset='{b}'. The model was trained with a different label "
                f"order; do not evaluate this checkpoint on this dataset.")
