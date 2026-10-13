"""Predictor service for the API.

Wraps the shared ``ml.predictor.Predictor`` (the exact class used by the
CLI) and adds the production safety check against the persisted
``class_names.json`` mapping: the checkpoint class count, order and names
must match the saved mapping, otherwise the service refuses to start.
"""
from __future__ import annotations

import logging
from pathlib import Path

from ml.model import CLASS_NAMES_PATH, verify_class_mapping
from ml.predictor import Predictor

logger = logging.getLogger("uvicorn.error")


class PredictorService:
    """Application-scoped inference service.

    Built once during the FastAPI lifespan; every request reuses the same
    loaded model. A failed construction means the model is not ready and
    ``/api/predict`` must fail with 503 instead of guessing.
    """

    def __init__(self, weights_path: Path, device: str = "auto",
                 class_names_path: Path = CLASS_NAMES_PATH) -> None:
        self.predictor = Predictor(weights_path=weights_path, device=device)
        self.class_names = self.predictor.class_names
        self.num_classes = self.predictor.num_classes
        self.device = str(self.predictor.device)

        if class_names_path and Path(class_names_path).exists():
            import json

            saved = json.loads(Path(class_names_path).read_text("utf-8"))
            verify_class_mapping(self.class_names, saved)
            logger.info("class mapping verified against %s (%d classes)",
                        class_names_path.name, self.num_classes)
        logger.info("model ready: %d classes on %s (weights: %s)",
                    self.num_classes, self.device,
                    Path(weights_path).name)

    def predict_pil(self, image, top_k: int = 3) -> dict:
        """Predict one decoded image; see ``ml.predictor.Predictor``."""
        return self.predictor.predict_pil(image, top_k=top_k)
