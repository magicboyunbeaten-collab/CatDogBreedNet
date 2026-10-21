"""Shared prediction service for the cat/dog breed classifier.

The ``Predictor`` class loads a checkpoint exactly once and can then serve
any number of images. It is the single inference path used by both the CLI
(``ml/predict.py``) and the FastAPI backend (``backend/app``), so training,
CLI and API preprocessing / class mapping / Top-K logic can never drift
apart.

Typical use::

    predictor = Predictor()                      # loads artifacts/best_model.pth
    result = predictor.predict_path("cat.jpg")  # {"predictions": [...], ...}
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

# Allow running as a plain script: python ml/predictor.py
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from PIL import Image  # noqa: E402

from ml.dataset import build_transforms  # noqa: E402
from ml.model import (  # noqa: E402
    BEST_WEIGHTS_PATH,
    load_checkpoint,
    resolve_device,
)
from ml.predict import load_image, predict_from_tensor  # noqa: E402


class Predictor:
    """Load a breed-classification checkpoint once and predict many images.

    Parameters
    ----------
    weights_path:
        Checkpoint saved by ``ml.train`` (default ``artifacts/best_model.pth``).
    device:
        ``"auto"`` (CUDA when available), ``"cpu"`` or ``"cuda"``.
    model_factory:
        Optional ``num_classes -> nn.Module`` factory, mainly for tests with
        lightweight stand-in models.
    """

    def __init__(self, weights_path: Path = BEST_WEIGHTS_PATH,
                 device: str = "auto", model_factory=None) -> None:
        self.weights_path = Path(weights_path)
        self.device = resolve_device(device)
        # Loaded exactly once per Predictor instance; the checkpoint carries
        # the authoritative class names and class count.
        self.model, self.class_names = load_checkpoint(
            self.weights_path, model_factory=model_factory, device=self.device)
        self.num_classes = len(self.class_names)
        # Serialize forward passes: single-GPU inference is not safe to run
        # fully concurrently without extra care (CODEBUDDY.md section 7.3).
        self._lock = threading.Lock()

    def predict_pil(self, image: Image.Image, top_k: int = 3) -> dict:
        """Predict one already-decoded RGB image.

        Returns ``{"predictions": [{"breed", "confidence"}...],
        "probabilities": {...}, "inference_ms": float,
        "preprocess_ms": float}`` where ``inference_ms`` covers the model
        forward pass only and ``preprocess_ms`` covers the deterministic eval
        transform. ``probabilities`` is the full softmax vector over the
        trained classes; it stays internal (the API schema never exposes it)
        and exists so look-alike candidate groups are not blind to candidates
        ranked below ``top_k``.
        """
        if not 1 <= top_k <= self.num_classes:
            raise ValueError(
                f"top_k must be between 1 and {self.num_classes}, got {top_k}")
        started = time.perf_counter()
        tensor = build_transforms(train=False)(image)
        preprocess_ms = (time.perf_counter() - started) * 1000
        with self._lock:
            result = predict_from_tensor(self.model, tensor, self.class_names,
                                         top_k=top_k, device=self.device)
        return {
            "predictions": result["predictions"],
            "probabilities": result.get("probabilities"),
            "inference_ms": result["elapsed_ms"],
            "preprocess_ms": round(preprocess_ms, 3),
        }

    def predict_path(self, image_path: Path, top_k: int = 3) -> dict:
        """Predict one image file (decoded via the shared loader)."""
        image = load_image(Path(image_path))
        return self.predict_pil(image, top_k=top_k)
