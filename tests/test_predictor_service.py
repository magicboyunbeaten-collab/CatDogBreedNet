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

    #: 记录最后一次构造收到的 image_size，供 U6.6 的分辨率透传用例断言。
    last_image_size: int | None = None

    def __init__(self, weights_path, device="auto", model_factory=None,
                 image_size=None):
        _FakeInnerPredictor.last_image_size = image_size
        self.weights_path = Path(weights_path)
        self.class_names = list(FAKE_CLASSES)
        self.num_classes = len(self.class_names)
        self.device = "cpu"
        self.image_size = image_size


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


# ---------------------------------------------------------------------------
# U5.5：类别**数量**错配（如 136 类权重配 37 类表）必须明确失败
# ---------------------------------------------------------------------------

def test_class_count_mismatch_names_both_sides(tmp_path, fake_predictor):
    """数量不同时的错误必须点明两个文件与两侧计数，不能只说 "failed"。"""
    weights = tmp_path / "best_model.pth"
    weights.write_bytes(b"")
    mapping = tmp_path / "class_names.json"
    # 假 checkpoint 是 3 类；故意只给 2 类
    mapping.write_text(json.dumps(["beagle", "boxer"]), encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        PredictorService(weights_path=weights, device="cpu",
                         class_names_path=mapping)

    message = str(excinfo.value)
    assert "class count mismatch" in message
    assert "3 classes" in message          # 权重侧
    assert "2 classes" in message          # 类名表侧
    assert "class_names.json" in message   # 指出是哪个文件配错
    assert "best_model.pth" in message     # 指出是哪个权重


def test_class_count_mismatch_does_not_silently_fall_back(tmp_path,
                                                          fake_predictor):
    """错配绝不能静默降级成"少几类也行"。"""
    weights = tmp_path / "best_model.pth"
    weights.write_bytes(b"")
    mapping = tmp_path / "class_names.json"
    mapping.write_text(json.dumps(FAKE_CLASSES + ["extra_breed"]),
                       encoding="utf-8")
    with pytest.raises(ValueError, match="class count mismatch"):
        PredictorService(weights_path=weights, device="cpu",
                         class_names_path=mapping)


# ---------------------------------------------------------------------------
# U6.4.1：类别**数量相同**但名称或顺序不匹配 —— 必须报索引级错误
# ---------------------------------------------------------------------------
# 与上面的"数量错配"是两条不同分支：
#   * 数量不同 -> "class count mismatch"（含两侧计数与两个文件名）
#   * 数量相同 -> 原样抛出 verify_class_mapping 的
#                 "class mapping mismatch at index N"（指名索引与两侧标签）
# 后者绝不能被误报成数量问题，否则运维会去改类别表规模而不是修正顺序。

def test_same_class_count_but_reordered_names_refuses_to_start(
        tmp_path, fake_predictor):
    """同数量、同一集合但**顺序反转** → 索引级错配，不得报数量错。

    ``FAKE_CLASSES = ["beagle", "boxer", "chihuahua"]``，
    这里把类别表写成 ``["chihuahua", "boxer", "beagle"]``：
    数量仍是 3，但 index 0 与 index 2 对调。
    """
    weights = tmp_path / "best_model.pth"
    weights.write_bytes(b"")
    mapping = tmp_path / "class_names.json"
    mapping.write_text(json.dumps(list(reversed(FAKE_CLASSES))),
                       encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        PredictorService(weights_path=weights, device="cpu",
                         class_names_path=mapping)

    message = str(excinfo.value)
    # 1) 保留 verify_class_mapping 的索引级信息（索引 + 两侧真实标签）
    assert "class mapping mismatch at index 0" in message
    assert "checkpoint='beagle'" in message
    assert "dataset='chihuahua'" in message
    # 2) 不得落入"数量不同"分支：数量相同却报数量错会误导运维
    assert "class count mismatch" not in message
    assert "classes" not in message


def test_same_class_count_but_different_name_refuses_to_start(
        tmp_path, fake_predictor):
    """同数量、仅**某一项名称不同** → 索引级错配，定位到具体 index。

    ``FAKE_CLASSES`` 的第 3 项是 ``chihuahua``，这里换成 ``pug``：
    只有 index 2 不同，前两项一致。
    """
    weights = tmp_path / "best_model.pth"
    weights.write_bytes(b"")
    mapping = tmp_path / "class_names.json"
    mapping.write_text(json.dumps(["beagle", "boxer", "pug"]),
                       encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        PredictorService(weights_path=weights, device="cpu",
                         class_names_path=mapping)

    message = str(excinfo.value)
    assert "class mapping mismatch at index 2" in message
    assert "checkpoint='chihuahua'" in message
    assert "dataset='pug'" in message
    # 前两项一致，绝不能报 index 0 或 index 1
    assert "at index 0" not in message
    assert "at index 1" not in message
    assert "class count mismatch" not in message


def test_same_class_count_mismatch_does_not_start_service(
        tmp_path, fake_predictor):
    """索引级错配时服务**不得被构造成功**（无静默回退、无自动重排）。"""
    weights = tmp_path / "best_model.pth"
    weights.write_bytes(b"")
    mapping = tmp_path / "class_names.json"
    mapping.write_text(json.dumps(list(reversed(FAKE_CLASSES))),
                       encoding="utf-8")

    service = None
    with pytest.raises(ValueError):
        service = PredictorService(weights_path=weights, device="cpu",
                                   class_names_path=mapping)
    # 异常抛出后绝不应留下一个"可用"的服务实例
    assert service is None



# ---------------------------------------------------------------------------
# U6.6：推理分辨率必须与权重的训练分辨率一致（exp06 为 256）
# ---------------------------------------------------------------------------

def test_image_size_is_passed_through_to_inner_predictor(
        tmp_path, fake_predictor):
    """服务层必须把 image_size 原样交给内层 Predictor。

    exp06 训练于 256；若服务仍按 224 预处理，macro-F1 会从 0.8149 掉到 0.8010，
    低于 V2.1 基线，切换就失去意义。因此这条透传必须被测试锁住。
    """
    weights = tmp_path / "best_model.pth"
    weights.write_bytes(b"")
    service = PredictorService(weights_path=weights, device="cpu",
                               class_names_path=None, image_size=256)
    assert service.image_size == 256
    assert _FakeInnerPredictor.last_image_size == 256


def test_image_size_defaults_to_project_standard_when_unspecified(
        tmp_path, fake_predictor):
    """不传 image_size 时保持 224（向后兼容既有调用点）。"""
    from ml.config import IMAGE_SIZE

    weights = tmp_path / "best_model.pth"
    weights.write_bytes(b"")
    service = PredictorService(weights_path=weights, device="cpu",
                               class_names_path=None)
    assert service.image_size == IMAGE_SIZE == 224
    assert _FakeInnerPredictor.last_image_size == 224


def test_startup_log_states_image_size(tmp_path, fake_predictor, caplog):
    """启动日志必须写明 image_size：换了权重却忘了改分辨率时能立刻看出。"""
    weights = tmp_path / "best_model.pth"
    weights.write_bytes(b"")
    with caplog.at_level(logging.INFO):
        PredictorService(weights_path=weights, device="cpu",
                         class_names_path=None, image_size=256)
    assert "image_size=256" in caplog.text


def test_service_exposes_version_id_for_health(tmp_path, fake_predictor):
    """U6.6：服务要把 model_version.json 的 version_id 暴露给健康接口。"""
    version_id = "v2_2_exp06_resolution256_lowlr_seed42"
    _write_version(tmp_path, {"version_id": version_id, "num_classes": 136})
    weights = tmp_path / "best_model.pth"
    weights.write_bytes(b"")
    service = PredictorService(weights_path=weights, device="cpu",
                               class_names_path=None, image_size=256)
    assert service.model_version["version_id"] == version_id


def test_service_model_version_is_none_without_version_file(
        tmp_path, fake_predictor):
    """没有版本文件时不得臆造版本（健康接口应返回 None）。"""
    weights = tmp_path / "best_model.pth"
    weights.write_bytes(b"")
    service = PredictorService(weights_path=weights, device="cpu",
                               class_names_path=None, image_size=256)
    assert service.model_version is None