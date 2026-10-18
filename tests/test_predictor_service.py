"""Unit tests for ``backend.app.services.predictor.PredictorService``.

These tests never download weights and never run real inference: the inner
``Predictor`` is replaced with a lightweight stand-in via monkeypatching, so
only the service's own behaviour (version-file reading, startup logging and
the class-mapping safety gate) is exercised.
"""
import json
import logging
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.services import predictor as predictor_module  # noqa: E402
from backend.app.services.predictor import (  # noqa: E402
    PredictorService,
    read_model_version,
)

FAKE_CLASSES = ["beagle", "boxer", "chihuahua"]


class _FakeInnerPredictor:
    """Stand-in for ``ml.predictor.Predictor`` (no weights, no inference)."""

    def __init__(self, weights_path, device="auto", model_factory=None):
        self.weights_path = Path(weights_path)
        self.class_names = list(FAKE_CLASSES)
        self.num_classes = len(self.class_names)
        self.device = "cpu"


@pytest.fixture
def fake_predictor(monkeypatch):
    monkeypatch.setattr(predictor_module, "Predictor", _FakeInnerPredictor)


def _write_version(tmp_path, payload):
    (tmp_path / "model_version.json").write_text(
        json.dumps(payload), encoding="utf-8")


# ---------------------------------------------------------------------------
# read_model_version
# ---------------------------------------------------------------------------

def test_read_model_version_returns_payload(tmp_path):
    _write_version(tmp_path, {"version_id": "v1_1_37_optimized",
                              "num_classes": 37})
    payload = read_model_version(tmp_path / "best_model.pth")
    assert payload["version_id"] == "v1_1_37_optimized"
    assert payload["num_classes"] 	== 37


def test_read_model_version_missing_file_returns_none(tmp_path):
    assert read_model_version(tmp_path / "best_model.pth") is None


def test_read_model_version_corrupt_file_returns_none(tmp_path, caplog):
    (tmp_path / "model_version.json").write_text("{ not json", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        assert read_model_version(tmp_path / "best_model.pth") is None
    assert "unreadable" in caplog.text


def test_read_model_version_non_dict_returns_none(tmp_path):
    (tmp_path / "model_version.json").write_text("[1, 2, 3]", encoding="utf-8")
    assert read_model_version(tmp_path / "best_model.pth") is None


# ---------------------------------------------------------------------------
# 启动日志：必须含版本与类别数，且不得暴露完整服务器路径
# ---------------------------------------------------------------------------

def test_startup_log_states_version_and_classes_without_full_path(
        tmp_path, fake_predictor, caplog):
    _write_version(tmp_path, {"version_id": "v1_1_37_optimized"})
    weights = tmp_path / "best_model.pth"
    weights.write_bytes(b"")          # 假权重：不会被真正读取
    with caplog.at_level(logging.INFO):
        service = PredictorService(weights_path=weights, device="cpu",
                                   class_names_path=None)
    assert service.num_classes == 3
    assert service.model_version["version_id"] == "v1_1_37_optimized"

    message = caplog.text
    assert "version=v1_1_37_optimized" in message
    assert "classes=3" in message
    # 只允许出现权重文件名，绝不允许出现完整服务器路径
    assert "best_model.pth" in message
    assert str(tmp_path) not in message


def test_startup_log_without_version_file_says_unknown(
        tmp_path, fake_predictor, caplog):
    weights = tmp_path / "best_model.pth"
    weights.write_bytes(b"")
    with caplog.at_level(logging.INFO):
        service = PredictorService(weights_path=weights, device="cpu",
                                   class_names_path=None)
    assert service.model_version is None
    assert "version=unknown" in caplog.text
    assert "classes=3" in caplog.text


def test_startup_log_with_corrupt_version_file_still_starts(
        tmp_path, fake_predictor, caplog):
    (tmp_path / "model_version.json").write_text("{ broken", encoding="utf-8")
    weights = tmp_path / "best_model.pth"
    weights.write_bytes(b"")
    with caplog.at_level(logging.INFO):
        service = PredictorService(weights_path=weights, device="cpu",
                                   class_names_path=None)
    assert service.num_classes == 3
    assert "version=unknown" in caplog.text


# ---------------------------------------------------------------------------
# 类别映射硬校验：不一致必须拒绝启动（切换安全网）
# ---------------------------------------------------------------------------

def test_mismatched_class_names_refuses_to_start(tmp_path, fake_predictor):
    weights = tmp_path / "best_model.pth"
    weights.write_bytes(b"")
    mapping = tmp_path / "class_names.json"
    mapping.write_text(json.dumps(["beagle", "boxer", "pug"]),
                       encoding="utf-8")   # 第 3 类与 checkpoint 不一致
    with pytest.raises(ValueError, match="class mapping mismatch"):
        PredictorService(weights_path=weights, device="cpu",
                         class_names_path=mapping)


def test_matching_class_names_starts(tmp_path, fake_predictor):
    weights = tmp_path / "best_model.pth"
    weights.write_bytes(b"")
    mapping = tmp_path / "class_names.json"
    mapping.write_text(json.dumps(FAKE_CLASSES), encoding="utf-8")
    service = PredictorService(weights_path=weights, device="cpu",
                              class_names_path=mapping)
    assert service.num_classes == 3
