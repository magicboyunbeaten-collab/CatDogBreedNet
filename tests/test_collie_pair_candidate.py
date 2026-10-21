"""U6.2：柯利牧羊犬 / 边境牧羊犬双候选提示的单元测试。

与 ``tests/test_candidate_group.py``（四类 bully 组）**完全独立**，覆盖
任务 §4.1 列出的 12 项要求：

1. Top-1=collie 且满足两个阈值时触发双候选；
2. Top-1=border_collie 且满足阈值时触发；
3. pair_margin 超阈值时不触发；
4. pair_mass 低于阈值时不触发；
5. Top-1 在两类外时不触发牧羊犬候选；
6. 两类组得分按完整概率归一化，和约为 100%（且不硬编码 50/50）；
7. Top-K 未包含某个候选时，仍从完整概率计算，不把该候选当作 0；
8. 原始 Top-1、Top-K、分数不被改写；
9. 四类 bully 候选组的成员、阈值、版本及代表样本行为不变；
10. V1.1 模式下安全返回，不崩溃；
11. 关闭总开关后两种候选均不显示；
12. API 不暴露完整概率向量，数据库 schema/写入不增加候选字段。

同样不使用模型权重与真实推理：所有用例手工构造 Top-K dict，
形状与 ``ml.predict.predict_from_tensor`` 的返回值一致。
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.schemas import CandidateGroupInfo, PredictResponse  # noqa: E402
from backend.app.services.candidate_group import (  # noqa: E402
    CANDIDATE_GROUP,
    CANDIDATE_GROUP_ZH,
    COLLIE_PAIR_GROUP,
    COLLIE_PAIR_GROUP_ZH,
    COLLIE_PAIR_MARGIN_THRESHOLD,
    COLLIE_PAIR_MASS_THRESHOLD,
    COLLIE_PAIR_VERSION,
    GROUP_ID_COLLIE_PAIR,
    GROUP_ID_FOUR_BREED,
    MARGIN_THRESHOLD,
    MASS_THRESHOLD,
    THRESHOLD_VERSION,
    build_candidate_group,
    build_collie_pair_group,
    resolve_candidate_group,
)

AMSTAFF = "american_staffordshire_terrier"
SBT = "staffordshire_bull_terrier"
AMBULL = "american_bulldog"
APBT = "american_pit_bull_terrier"
COLLIE = "collie"
BORDER_COLLIE = "border_collie"

#: 136 类空间中包含全部四类 bully 标签。
FULL_CLASSES = [APBT, AMSTAFF, SBT, AMBULL, "beagle", "boxer"]

#: 37 类 V1.1 空间：不含 collie / border_collie。
V11_CLASSES = [APBT, SBT, AMBULL, "beagle", "boxer", "chihuahua"]

#: 含两类牧羊犬标签的空间。
PAIR_CLASSES = [COLLIE, BORDER_COLLIE, "beagle", "boxer"]


def _pair_predictions(*pairs):
    """构造牧羊犬双候选场景的 Top-K 列表。"""
    return [{"breed": breed, "confidence": round(score, 6)}
            for breed, score in pairs]


def _bully_predictions():
    """U5.1 实际触发样本口径的四类代表样本。"""
    return [{"breed": breed, "confidence": round(score, 6)}
            for breed, score in ((APBT, 0.42), (AMSTAFF, 0.30),
                                 (SBT, 0.18), (AMBULL, 0.06))]


# ---------------------------------------------------------------------------
# 1. 成员与版本独立性
# ---------------------------------------------------------------------------

def test_collie_pair_members_and_version_are_independent():
    """两类组成员、阈值与版本必须与四类组明确区分（任务 §3.1）。"""
    assert COLLIE_PAIR_GROUP == ("collie", "border_collie")
    assert set(COLLIE_PAIR_GROUP).isdisjoint(set(CANDIDATE_GROUP))
    assert COLLIE_PAIR_VERSION != THRESHOLD_VERSION
    assert COLLIE_PAIR_VERSION == "val-2026-10-21-collie-pair-v1"
    assert set(COLLIE_PAIR_GROUP_ZH) == set(COLLIE_PAIR_GROUP)
    assert COLLIE_PAIR_GROUP_ZH[COLLIE] == "柯利牧羊犬"
    assert COLLIE_PAIR_GROUP_ZH[BORDER_COLLIE] == "边境牧羊犬"
    assert COLLIE_PAIR_MASS_THRESHOLD == 0.30
    assert COLLIE_PAIR_MARGIN_THRESHOLD == 0.30


# ---------------------------------------------------------------------------
# 2-5. 触发与不触发
# ---------------------------------------------------------------------------

def test_collie_pair_triggers_when_top1_collie_and_thresholds_met():
    """Top-1=collie 且质量/分差均满足时触发双候选（§4.1-1）。"""
    predictions = _pair_predictions((COLLIE, 0.6032), (BORDER_COLLIE, 0.3955))
    group = build_collie_pair_group(
        predictions, class_names=PAIR_CLASSES,
        probabilities={COLLIE: 0.6032, BORDER_COLLIE: 0.3955,
                       "beagle": 0.001})
    assert group is not None
    assert group["triggered"] is True
    assert group["group_id"] == GROUP_ID_COLLIE_PAIR
    assert group["group_id"] == "collie-pair"
    assert group["threshold_version"] == COLLIE_PAIR_VERSION
    assert group["top1_breed"] == COLLIE
    assert len(group["candidates"]) == 2


def test_collie_pair_triggers_when_top1_border_collie():
    """Top-1=border_collie 且满足阈值时触发（§4.1-2）。"""
    predictions = _pair_predictions((BORDER_COLLIE, 0.4107), (COLLIE, 0.1582))
    group = build_collie_pair_group(
        predictions, class_names=PAIR_CLASSES,
        probabilities={BORDER_COLLIE: 0.4107, COLLIE: 0.1582})
    assert group is not None
    assert group["triggered"] is True
    assert group["top1_breed"] == BORDER_COLLIE
    assert group["group_mass"] == pytest.approx(0.5689, abs=1e-6)
    assert group["group_margin"] == pytest.approx(0.2525, abs=1e-6)


def test_collie_pair_not_triggered_when_margin_too_large():
    """pair_margin 超阈值时不触发（§4.1-3）。"""
    predictions = _pair_predictions((COLLIE, 0.90), (BORDER_COLLIE, 0.02))
    group = build_collie_pair_group(
        predictions, class_names=PAIR_CLASSES,
        probabilities={COLLIE: 0.90, BORDER_COLLIE: 0.02})
    assert group is not None
    assert group["triggered"] is False
    assert "分差" in group["reason"]


def test_collie_pair_not_triggered_when_mass_too_low():
    """pair_mass 低于阈值时不触发（§4.1-4）。"""
    predictions = _pair_predictions((COLLIE, 0.20), (BORDER_COLLIE, 0.05))
    group = build_collie_pair_group(
        predictions, class_names=PAIR_CLASSES,
        probabilities={COLLIE: 0.20, BORDER_COLLIE: 0.05})
    assert group is not None
    assert group["triggered"] is False
    assert "总概率" in group["reason"]
    assert group["group_mass"] == pytest.approx(0.25, abs=1e-6)


def test_collie_pair_not_triggered_when_top1_outside_pair():
    """Top-1 在两类外时不触发牧羊犬候选（§4.1-5）。"""
    predictions = _pair_predictions(("beagle", 0.60), (COLLIE, 0.20))
    assert build_collie_pair_group(
        predictions, class_names=PAIR_CLASSES,
        probabilities={"beagle": 0.60, COLLIE: 0.20,
                       BORDER_COLLIE: 0.19}) is None


# ---------------------------------------------------------------------------
# 6-8. 归一化、Top-K 外候选、不改写原始预测
# ---------------------------------------------------------------------------

def test_collie_pair_scores_normalised_from_full_probabilities():
    """两类组得分按完整概率归一化且和约为 100%（§4.1-6）。

    同时验证**不硬编码 50/50**：0.6032 / 0.3955 归一化后必须是
    60.3985 / 39.6015，而不是各 50。
    """
    predictions = _pair_predictions((COLLIE, 0.6032), (BORDER_COLLIE, 0.3955))
    group = build_collie_pair_group(
        predictions, class_names=PAIR_CLASSES,
        probabilities={COLLIE: 0.6032, BORDER_COLLIE: 0.3955})
    scores = {item["breed"]: item["group_score"]
              for item in group["candidates"]}
    assert scores[COLLIE] == pytest.approx(60.3985, abs=1e-3)
    assert scores[BORDER_COLLIE] == pytest.approx(39.6015, abs=1e-3)
    assert sum(scores.values()) == pytest.approx(100.0, abs=1e-6)
    for item in group["candidates"]:
        expected = item["original_confidence"] / group["group_mass"] * 100
        assert item["group_score"] == pytest.approx(expected, abs=1e-3)


def test_collie_pair_candidate_outside_topk_uses_real_probability():
    """Top-K 未包含某个候选时仍从完整概率计算，不当 0（§4.1-7）。"""
    # border_collie 只出现在完整概率里，Top-K 中只有 collie 与 beagle
    predictions = _pair_predictions((COLLIE, 0.40), ("beagle", 0.25))
    group = build_collie_pair_group(
        predictions, class_names=PAIR_CLASSES,
        probabilities={COLLIE: 0.40, BORDER_COLLIE: 0.35, "beagle": 0.25})
    border = next(item for item in group["candidates"]
                  if item["breed"] == BORDER_COLLIE)
    assert border["original_confidence"] == pytest.approx(0.35, abs=1e-6)
    assert border["group_score"] > 0
    assert group["group_mass"] == pytest.approx(0.75, abs=1e-6)


def test_collie_pair_does_not_modify_original_predictions():
    """原始 Top-1、Top-K 与分数不被改写（§4.1-8）。"""
    predictions = _pair_predictions((COLLIE, 0.6032), (BORDER_COLLIE, 0.3955))
    before = json.dumps(predictions, sort_keys=True)
    group = build_collie_pair_group(
        predictions, class_names=PAIR_CLASSES,
        probabilities={COLLIE: 0.6032, BORDER_COLLIE: 0.3955})
    assert json.dumps(predictions, sort_keys=True) == before
    assert group["top1_confidence"] == pytest.approx(0.6032, abs=1e-6)


# ---------------------------------------------------------------------------
# 9. 四类组回归固化
# ---------------------------------------------------------------------------

def test_four_breed_group_unchanged_by_collie_pair():
    """四类 bully 组的成员、阈值、版本及代表样本行为不变（§4.1-9）。"""
    assert CANDIDATE_GROUP == (APBT, AMSTAFF, SBT, AMBULL)
    assert MASS_THRESHOLD == 0.30
    assert MARGIN_THRESHOLD == 0.40
    assert THRESHOLD_VERSION == "val-2026-10-19-four-breed-b1"
    assert len(CANDIDATE_GROUP_ZH) == 4

    group = build_candidate_group(_bully_predictions(),
                                  class_names=FULL_CLASSES)
    assert group["triggered"] is True
    assert group["group_id"] == GROUP_ID_FOUR_BREED
    assert group["threshold_version"] == THRESHOLD_VERSION
    assert len(group["candidates"]) == 4
    assert {item["breed"] for item in group["candidates"]} == set(CANDIDATE_GROUP)
    assert sum(item["group_score"]
               for item in group["candidates"]) == pytest.approx(100.0, abs=1e-6)


# ---------------------------------------------------------------------------
# 10-12. V1.1 安全、开关关闭、API 不暴露概率
# ---------------------------------------------------------------------------

def test_collie_pair_returns_none_for_v11_class_space():
    """V1.1（37 类）不含两类标签时安全返回 None，不抛异常（§4.1-10）。"""
    predictions = _pair_predictions((COLLIE, 0.60), (BORDER_COLLIE, 0.39))
    assert build_collie_pair_group(predictions, class_names=V11_CLASSES,
                                   probabilities={COLLIE: 0.60}) is None


def test_resolve_dispatch_selects_strategy_by_top1():
    """按原始 Top-1 分发：四类走四类逻辑，两类走双候选逻辑，其它不展示。"""
    pair_result = {
        "predictions": _pair_predictions((COLLIE, 0.6032),
                                         (BORDER_COLLIE, 0.3955)),
        "probabilities": {COLLIE: 0.6032, BORDER_COLLIE: 0.3955},
    }
    pair_group = resolve_candidate_group(pair_result, class_names=PAIR_CLASSES,
                                         enabled=True)
    assert pair_group["group_id"] == GROUP_ID_COLLIE_PAIR
    assert len(pair_group["candidates"]) == 2

    bully_group = resolve_candidate_group(
        {"predictions": _bully_predictions()},
        class_names=FULL_CLASSES, enabled=True)
    assert bully_group["group_id"] == GROUP_ID_FOUR_BREED
    assert len(bully_group["candidates"]) == 4

    assert resolve_candidate_group(
        {"predictions": [{"breed": "beagle", "confidence": 0.90}]},
        class_names=PAIR_CLASSES, enabled=True) is None


def test_master_switch_disables_both_strategies():
    """关闭总开关后两种候选均不显示（§4.1-11）。"""
    pair_result = {
        "predictions": _pair_predictions((COLLIE, 0.6032),
                                         (BORDER_COLLIE, 0.3955)),
        "probabilities": {COLLIE: 0.6032, BORDER_COLLIE: 0.3955},
    }
    assert resolve_candidate_group(pair_result, class_names=PAIR_CLASSES,
                                   enabled=False) is None
    assert resolve_candidate_group(
        {"predictions": _bully_predictions()},
        class_names=FULL_CLASSES, enabled=False) is None


def test_api_response_never_exposes_full_probability_vector():
    """API 不暴露完整概率向量，DB 写入不增加候选字段（§4.1-12）。"""
    predictions = _pair_predictions((COLLIE, 0.6032), (BORDER_COLLIE, 0.3955))
    group = build_collie_pair_group(
        predictions, class_names=PAIR_CLASSES,
        probabilities={COLLIE: 0.6032, BORDER_COLLIE: 0.3955,
                       "beagle": 0.001, "boxer": 0.0005})
    # 响应里只应出现两个候选，绝不能出现完整概率字典
    assert "probabilities" not in group
    assert len(group["candidates"]) == 2
    assert set(group) == {
        "group_id", "triggered", "threshold_version", "top1_breed",
        "top1_confidence", "candidates", "available_candidates",
        "group_mass", "group_margin", "reason",
    }
    response = PredictResponse(
        success=True,
        predictions=predictions,
        num_classes=136,
        top_k=len(predictions),
        inference_ms=1.0,
        preprocess_ms=1.0,
        elapsed_ms=2.0,
        record_id=1,
        candidate_group=CandidateGroupInfo(**group),
    )
    dumped = response.model_dump()
    assert "probabilities" not in dumped
    assert dumped["candidate_group"]["group_id"] == "collie-pair"


def test_candidate_group_info_group_id_is_optional():
    """group_id 为可选字段，旧响应（无该字段）仍能通过 schema 校验。"""
    legacy = CandidateGroupInfo(
        triggered=True,
        threshold_version="val-2026-10-19-four-breed-b1",
        top1_breed=APBT,
        top1_confidence=0.42,
        candidates=[{"breed": APBT, "breed_zh": "美国比特斗牛梗",
                     "original_confidence": 0.42, "group_score": 100.0}],
        available_candidates=list(CANDIDATE_GROUP),
        group_mass=0.42,
        group_margin=0.0,
        reason="test",
    )
    assert legacy.group_id is None
