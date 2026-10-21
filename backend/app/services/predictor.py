"""Predictor service for the API.

Wraps the shared ``ml.predictor.Predictor`` (the exact class used by the
CLI) and adds the production safety check against the persisted
``class_names.json`` mapping: the checkpoint class count, order and names
must match the saved mapping, otherwise the service refuses to start.

It also reads an optional ``model_version.json`` next to the weights so the
startup log can state *which* model version is serving traffic. Only the
version id and the weights **file name** are logged — never a full server
path — so the log stays useful for operators without leaking deployment
details.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ml.model import CLASS_NAMES_PATH, verify_class_mapping
from ml.predictor import Predictor

logger = logging.getLogger("uvicorn.error")

VERSION_FILE_NAME = "model_version.json"


def read_model_version(weights_path: Path) -> dict | None:
    """Read ``model_version.json`` next to the weights, if present.

    Returns ``None`` when the file is absent or unreadable; callers must keep
    working in that case (deployments without a version file still start).
    """
    version_file = Path(weights_path).parent / VERSION_FILE_NAME
    if not version_file.exists():
        return None
    try:
        payload = json.loads(version_file.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - 版本文件损坏不应阻止服务启动
        logger.warning("model version file unreadable: %s",
                       VERSION_FILE_NAME)
        return None
    return payload if isinstance(payload, dict) else None


class PredictorService:
    """Application-scoped inference service.

    Built once during the FastAPI lifespan; every request reuses the same
    loaded model. A failed construction means the model is not ready and
    ``/api/predict`` must fail with 503 instead of guessing.
    """

    def __init__(self, weights_path: Path, device: str = "auto",
                 class_names_path: Path = CLASS_NAMES_PATH,
                 candidate_group_enabled: bool = False) -> None:
        self.weights_path = Path(weights_path)
        self.predictor = Predictor(weights_path=self.weights_path, device=device)
        self.class_names = self.predictor.class_names
        self.num_classes = self.predictor.num_classes
        self.device = str(self.predictor.device)
        #: 相近犬种候选组开关（默认关闭；开启也不改变模型、权重或类别定义）。
        self.candidate_group_enabled = bool(candidate_group_enabled)
        self.model_version = read_model_version(self.weights_path)
        version_id = (self.model_version or {}).get("version_id", "unknown")

        if class_names_path and Path(class_names_path).exists():
            saved = json.loads(Path(class_names_path).read_text("utf-8"))
            try:
                verify_class_mapping(self.class_names, saved)
            except ValueError as exc:
                # 类别**数量**不同是配置层面的错配（例如 136 类权重配了 37
                # 类表），必须点明是两个文件、两侧计数；数量相同但名称/顺序
                # 不同则保留 verify_class_mapping 原有的索引级错误消息。
                if len(self.class_names) != len(saved):
                    raise ValueError(
                        f"class count mismatch between checkpoint and class "
                        f"names file: weights={self.weights_path} "
                        f"({len(self.class_names)} classes), "
                        f"class_names={class_names_path} "
                        f"({len(saved)} classes). "
                        f"Point CATDOG_WEIGHTS_PATH and CATDOG_CLASS_NAMES_PATH "
                        f"at a matching pair."
                    ) from exc
                raise
            logger.info("class mapping verified against %s (%d classes)",
                        class_names_path.name, self.num_classes)
        # 只打印版本 ID 与权重文件名，不暴露完整服务器路径
        logger.info("model ready: version=%s arch=resnet18 classes=%d "
                    "device=%s (weights: %s)",
                    version_id, self.num_classes, self.device,
                    self.weights_path.name)

    def predict_pil(self, image, top_k: int = 3) -> dict:
        """Predict one decoded image; see ``ml.predictor.Predictor``."""
        return self.predictor.predict_pil(image, top_k=top_k)

    def candidate_group(self, result: dict) -> dict | None:
        """Candidate-group info for a prediction result, if the feature is on.

        Returns ``None`` when the feature is disabled or the trigger conditions
        are not met, so the caller can keep the legacy response shape.
        """
        from .candidate_group import resolve_candidate_group

        return resolve_candidate_group(
            result, class_names=self.class_names,
            enabled=self.candidate_group_enabled)
