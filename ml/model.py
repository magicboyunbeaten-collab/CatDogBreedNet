"""Model construction and checkpoint utilities.

The baseline is torchvision's ResNet18 with ImageNet pretrained weights and
a replaced fully-connected head producing ``num_classes`` logits.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

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


def build_model(num_classes: int, pretrained: bool = True) -> nn.Module:
    """Build ResNet18 with an ``num_classes``-way classification head.

    Raises ``RuntimeError`` if the pretrained weights cannot be obtained
    (e.g. download failure) -- we never silently fall back to random
    initialization (CODEBUDDY.md 6.4).
    """
    if num_classes < 2:
        raise ValueError(f"num_classes must be >= 2, got {num_classes}")
    try:
        weights = (models.ResNet18_Weights.IMAGENET1K_V1 if pretrained else None)
        model = models.resnet18(weights=weights)
    except Exception as exc:  # download / hub errors surface here
        raise RuntimeError(
            f"failed to obtain pretrained ResNet18 weights ({type(exc).__name__}: {exc}). "
            "Check network access to download.pytorch.org and that TORCH_HOME "
            "points to a writable directory. Refusing to fall back to random "
            "weights silently.") from exc
    model.fc = nn.Linear(model.fc.in_features, num_classes)
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
    if arch == ARCH:
        return lambda num_classes: build_model(num_classes, pretrained=False)
    raise ValueError(
        f"unsupported checkpoint arch '{arch}'; pass an explicit "
        f"model_factory(num_classes) to load_checkpoint().")


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
