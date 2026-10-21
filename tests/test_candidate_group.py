"""Unit tests for the look-alike candidate group (U5).

Covers the eight behaviours required by the task sheet:

1. top-1 in the group + ambiguity thresholds met  -> triggered;
2. group scores sum to 100 %;
3. group scores come from normalising the raw probabilities without
   modifying the original prediction array;
4. low group mass or a large within-group gap -> not triggered;
5. top-1 outside the group -> handled by definition;
6. a 37-class space without AmStaff -> no error, legacy behaviour;
7. a user selection never overwrites the model prediction;
8. existing predict / history / stats / breed-name / training tests keep
   passing (this file adds no regression of its own).

No model weights and no real inference are used: every case feeds hand-made
Top-K dicts, exactly like ``ml.predict.predict_from_tensor`` would return.
"""
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
    COLLIE_PAIR_SHARE_THRESHOLD,
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

#: A 136-class space that contains every candidate label.
FULL_CLASSES = [APBT, AMSTAFF, SBT, AMBULL, "beagle", "boxer"]

#: The 37-class V1.1 space: it has SBT and American Bulldog but NOT AmStaff.
V11_CLASSES = [APBT, SBT, AMBULL, "beagle", "boxer", "chihuahua"]

#: A space that contains both牧羊犬 labels (needed by the collie-pair strategy).
PAIR_CLASSES = [COLLIE, BORDER_COLLIE, "beagle", "boxer"]


def _predictions(*pairs):
    """Build a Top-K list exactly like ``predict_from_tensor`` returns."""
    return [{"breed": breed, "confidence": confidence}
            for breed, confidence in pairs]


def _ambiguous_group():
    """top-1 in the group, decent mass, small within-group gap."""
    return _predictions(
        (AMSTAFF, 0.34), (SBT, 0.30), (AMBULL, 0.26), (APBT, 0.05),
        ("beagle", 0.03))


# ---------------------------------------------------------------------------
# 1. triggered when top-1 is in the group and the ambiguity thresholds hold
# ---------------------------------------------------------------------------

def test_triggers_when_top1_in_group_and_ambiguous():
    group = build_candidate_group(_ambiguous_group(), class_names=FULL_CLASSES)
    assert group is not None
    assert group["triggered"] is True
    assert group["top1_breed"] == AMSTAFF
    assert group["top1_confidence"] == 0.34
    assert set(group["available_candidates"]) == set(CANDIDATE_GROUP)
    assert group["threshold_version"]
    assert group["reason"]


def test_group_mass_and_margin_are_reported():
    """四类候选组：APBT 的 0.05 也计入 group_mass。"""
    group = build_candidate_group(_ambiguous_group(), class_names=FULL_CLASSES)
    assert group["group_mass"] == pytest.approx(0.95, abs=1e-6)
    assert group["group_margin"] == pytest.approx(0.04, abs=1e-6)
    assert len(group["candidates"]) == 4


# ---------------------------------------------------------------------------
# 2. group scores sum to 100 %
# ---------------------------------------------------------------------------

def test_group_scores_sum_to_100():
    group = build_candidate_group(_ambiguous_group(), class_names=FULL_CLASSES)
    total = sum(item["group_score"] for item in group["candidates"])
    assert total == pytest.approx(100.0, abs=1e-6)


def test_group_scores_sum_to_100_with_uneven_mass():
    group = build_candidate_group(
        _predictions((AMBULL, 0.62), (SBT, 0.30), (AMSTAFF, 0.05)),
        class_names=FULL_CLASSES)
    total = sum(item["group_score"] for item in group["candidates"])
    assert total == pytest.approx(100.0, abs=1e-6)


def test_group_scores_are_relative_not_overall_confidence():
    """A candidate with 10 % raw mass must NOT show 10 % group score."""
    group = build_candidate_group(
        _predictions((AMBULL, 0.60), (SBT, 0.30), (AMSTAFF, 0.10)),
        class_names=FULL_CLASSES)
    scores = {item["breed"]: item["group_score"] for item in group["candidates"]}
    assert scores[AMBULL] == pytest.approx(60.0, abs=1e-3)
    assert scores[SBT] == pytest.approx(30.0, abs=1e-3)
    assert scores[AMSTAFF] == pytest.approx(10.0, abs=1e-3)
    # raw softmax is preserved next to the relative score
    raws = {item["breed"]: item["original_confidence"]
            for item in group["candidates"]}
    assert raws[AMSTAFF] == pytest.approx(0.10, abs=1e-6)


def test_every_candidate_carries_a_chinese_name():
    group = build_candidate_group(_ambiguous_group(), class_names=FULL_CLASSES)
    for item in group["candidates"]:
        assert item["breed_zh"] == CANDIDATE_GROUP_ZH[item["breed"]]
        assert item["breed_zh"].strip()


# ---------------------------------------------------------------------------
# 3. the raw probability vector is never modified
# ---------------------------------------------------------------------------

def test_original_predictions_are_not_modified():
    predictions = _ambiguous_group()
    before = [dict(item) for item in predictions]
    build_candidate_group(predictions, class_names=FULL_CLASSES)
    assert predictions == before
    # order preserved: still the model's own Top-K order
    assert [item["breed"] for item in predictions] == [
        item["breed"] for item in before]


def test_candidates_are_sorted_by_group_score_descending():
    group = build_candidate_group(_ambiguous_group(), class_names=FULL_CLASSES)
    scores = [item["group_score"] for item in group["candidates"]]
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# 4. not triggered on low mass or a large within-group gap
# ---------------------------------------------------------------------------

def test_not_triggered_when_group_mass_too_low():
    predictions = _predictions(
        (AMSTAFF, 0.10), (SBT, 0.08), (AMBULL, 0.07), (APBT, 0.02),
        ("beagle", 0.10))
    group = build_candidate_group(predictions, class_names=FULL_CLASSES)
    assert group is not None
    assert group["triggered"] is False
    assert "总概率" in group["reason"]
    # 四类之和 = 0.10+0.08+0.07+0.02 = 0.27 < 0.30
    assert group["group_mass"] == pytest.approx(0.27, abs=1e-6)


def test_not_triggered_when_within_group_gap_too_large():
    predictions = _predictions(
        (AMSTAFF, 0.80), (SBT, 0.05), (AMBULL, 0.03), ("beagle", 0.10))
    group = build_candidate_group(predictions, class_names=FULL_CLASSES)
    assert group is not None
    assert group["triggered"] is False
    assert "分差" in group["reason"]
    assert group["group_margin"] == pytest.approx(0.75, abs=1e-6)


def test_not_triggered_when_both_conditions_fail():
    predictions = _predictions(
        (AMSTAFF, 0.10), (SBT, 0.05), (APBT, 0.03), ("beagle", 0.20))
    group = build_candidate_group(predictions, class_names=FULL_CLASSES)
    # 四类之和 = 0.10+0.05+0.03 = 0.18 < 0.30（APBT 不在 Top-3，按 0 计）
    assert group["group_mass"] == pytest.approx(0.18, abs=1e-6)
    assert group["triggered"] is False


def test_mass_threshold_boundary_is_inclusive():
    """组内总质量恰好等于阈值时应触发（>= 语义）。"""
    predictions = _predictions(
        (AMSTAFF, 0.16), (SBT, 0.14), (AMBULL, 0.0), (APBT, 0.0))
    group = build_candidate_group(predictions, class_names=FULL_CLASSES)
    assert group["group_mass"] == pytest.approx(MASS_THRESHOLD, abs=1e-9)
    assert group["group_margin"] == pytest.approx(0.02, abs=1e-9)
    assert group["triggered"] is True


def test_margin_threshold_boundary_is_inclusive():
    """组内分差恰好等于阈值时应触发（<= 语义）。"""
    predictions = _predictions(
        (AMSTAFF, 0.70), (SBT, 0.30), (AMBULL, 0.0), ("beagle", 0.0))
    group = build_candidate_group(predictions, class_names=FULL_CLASSES)
    assert group["group_margin"] == pytest.approx(MARGIN_THRESHOLD, abs=1e-9)
    assert group["triggered"] is True


# ---------------------------------------------------------------------------
# 5. top-1 outside the group
# ---------------------------------------------------------------------------

def test_top1_outside_group_is_not_triggered():
    """Top-1 为组外犬种（beagle）时不触发，即使四个候选合计概率很高。"""
    predictions = _predictions(
        ("beagle", 0.55), (APBT, 0.20), (AMSTAFF, 0.15), (SBT, 0.05))
    group = build_candidate_group(predictions, class_names=FULL_CLASSES)
    assert group is not None
    assert group["triggered"] is False
    assert group["reason"] == "top-1 不在候选组内"
    # the candidate list is still returned so the UI *could* show context
    assert {item["breed"] for item in group["candidates"]} == set(CANDIDATE_GROUP)


def test_top1_outside_group_keeps_top1_breed_untouched():
    predictions = _predictions(("beagle", 0.70), (AMSTAFF, 0.10))
    group = build_candidate_group(predictions, class_names=FULL_CLASSES)
    assert group["top1_breed"] == "beagle"
    assert group["top1_confidence"] == 0.70


def test_candidate_absent_from_topk_counts_as_zero():
    """A candidate missing from Top-K has an unknown raw score -> 0."""
    predictions = _predictions((SBT, 0.40), (AMBULL, 0.30),
                               ("beagle", 0.20))
    group = build_candidate_group(predictions, class_names=FULL_CLASSES)
    amstaff = next(item for item in group["candidates"]
                   if item["breed"] == AMSTAFF)
    assert amstaff["original_confidence"] == 0.0
    assert amstaff["group_score"] == 0.0


# ---------------------------------------------------------------------------
# U5.2：四类候选组专属用例（方案 B1）
# ---------------------------------------------------------------------------

def test_four_breed_group_members_are_exact():
    """候选组必须恰为四项且 canonical label 正确（任务单 4.1-1）。"""
    assert len(CANDIDATE_GROUP) == 4
    assert set(CANDIDATE_GROUP) == {
        "american_pit_bull_terrier",
        "american_staffordshire_terrier",
        "staffordshire_bull_terrier",
        "american_bulldog",
    }
    # 顺序固定：APBT 在最前，其余保持原有顺序
    assert CANDIDATE_GROUP[0] == APBT
    assert set(CANDIDATE_GROUP_ZH) == set(CANDIDATE_GROUP)


def test_four_breed_group_has_chinese_names_for_every_member():
    """每一项候选都必须有非空中文名（任务单 4.1-1 / 前端展示依赖）。"""
    for label in CANDIDATE_GROUP:
        assert CANDIDATE_GROUP_ZH[label].strip()
    assert CANDIDATE_GROUP_ZH[APBT] == "美国比特斗牛梗"


def test_top1_apbt_triggers_when_thresholds_met():
    """Top-1 为 APBT 且满足阈值时必须触发（任务单 4.1-4）。"""
    predictions = _predictions(
        (APBT, 0.40), (AMSTAFF, 0.35), (SBT, 0.20), (AMBULL, 0.03))
    group = build_candidate_group(predictions, class_names=FULL_CLASSES)
    assert group is not None
    assert group["triggered"] is True
    assert group["top1_breed"] == APBT
    assert len(group["candidates"]) == 4
    # 触发时原始 Top-1 与 predictions[0] 一致（任务单 4.1-7）
    assert group["top1_breed"] == predictions[0]["breed"]
    assert group["top1_confidence"] == predictions[0]["confidence"]


def test_top1_apbt_does_not_trigger_when_group_margin_too_large():
    """Top-1 为 APBT 但组内已明显偏好时仍不触发。"""
    predictions = _predictions(
        (APBT, 0.85), (AMSTAFF, 0.05), (SBT, 0.03), (AMBULL, 0.01))
    group = build_candidate_group(predictions, class_names=FULL_CLASSES)
    assert group["triggered"] is False
    assert "分差" in group["reason"]


def test_four_breed_scores_sum_to_100_and_match_normalisation():
    """四类组内得分合计约 100，且严格等于 p_i/group_mass*100（任务单 4.1-6）。"""
    predictions = _predictions(
        (APBT, 0.42), (AMSTAFF, 0.30), (SBT, 0.18), (AMBULL, 0.06))
    group = build_candidate_group(predictions, class_names=FULL_CLASSES)
    total = sum(item["group_score"] for item in group["candidates"])
    assert total == pytest.approx(100.0, abs=1e-6)
    for item in group["candidates"]:
        expected = item["original_confidence"] / group["group_mass"] * 100
        assert item["group_score"] == pytest.approx(expected, abs=1e-3)


def test_four_breed_candidate_outside_topk_uses_real_probability():
    """完整概率中 APBT 排名在 Top-3 之外时，仍用其真实概率而非 0（任务单 4.1-2）。"""
    predictions = _predictions(
        (AMSTAFF, 0.40), (SBT, 0.30), (AMBULL, 0.20))
    probabilities = {APBT: 0.06, AMSTAFF: 0.40, SBT: 0.30, AMBULL: 0.20,
                     "beagle": 0.04}
    group = build_candidate_group(predictions, class_names=FULL_CLASSES,
                                  probabilities=probabilities)
    apbt = next(item for item in group["candidates"] if item["breed"] == APBT)
    assert apbt["original_confidence"] == pytest.approx(0.06, abs=1e-6)
    assert apbt["group_score"] == pytest.approx(0.06 / 0.96 * 100, abs=1e-3)
    assert group["group_mass"] == pytest.approx(0.96, abs=1e-6)


def test_top1_outside_four_group_with_partial_mass_does_not_trigger():
    """Top-1 组外时，即使四个候选合计概率很高也不触发（任务单 4.1-5）。"""
    predictions = _predictions(
        ("beagle", 0.30), (APBT, 0.25), (AMSTAFF, 0.20), (SBT, 0.15))
    group = build_candidate_group(predictions, class_names=FULL_CLASSES)
    assert group is not None
    assert group["triggered"] is False
    assert group["reason"] == "top-1 不在候选组内"
    assert group["group_mass"] == pytest.approx(0.60, abs=1e-6)


def test_v11_37_class_space_missing_apbt_returns_none():
    """V1.1（37 类）同时缺 APBT 与 AmStaff，必须安全返回 None（任务单 4.1-8）。"""
    predictions = _predictions(
        (APBT, 0.40), (AMSTAFF, 0.30), (SBT, 0.20), (AMBULL, 0.05))
    group = build_candidate_group(predictions, class_names=V11_CLASSES)
    assert group is None


def test_class_space_with_three_of_four_members_returns_none():
    """只缺任一成员（如仅缺 APBT）也不构成完整四类候选组。"""
    classes = [AMSTAFF, SBT, AMBULL, "beagle", "boxer"]
    predictions = _predictions(
        (AMSTAFF, 0.40), (SBT, 0.30), (AMBULL, 0.20))
    assert build_candidate_group(predictions, class_names=classes) is None


def test_threshold_version_marks_the_four_breed_b1_strategy():
    """threshold_version 必须可追溯到 U5.2 方案 B1。"""
    group = build_candidate_group(_ambiguous_group(), class_names=FULL_CLASSES)
    assert group["threshold_version"] == "val-2026-10-19-four-breed-b1"


# ---------------------------------------------------------------------------
# full probability vector (avoids treating out-of-top-K candidates as zero)
# ---------------------------------------------------------------------------

def test_full_probability_vector_is_used_when_provided():
    """A candidate ranked below top_k must not be shown as 0 %.

    Without the full vector AmStaff (rank 5) would read 0.0 and the group
    score would claim the model gave it nothing, which misrepresents the
    model output.
    """
    predictions = _predictions(
        (SBT, 0.40), (AMBULL, 0.30), (APBT, 0.20))
    probabilities = {APBT: 0.20, SBT: 0.40, AMBULL: 0.30, AMSTAFF: 0.08,
                     "beagle": 0.02}
    group = build_candidate_group(predictions, class_names=FULL_CLASSES,
                                  probabilities=probabilities)
    amstaff = next(item for item in group["candidates"]
                   if item["breed"] == AMSTAFF)
    assert amstaff["original_confidence"] == pytest.approx(0.08, abs=1e-6)
    # 四类之和 = 0.20+0.40+0.30+0.08 = 0.98
    assert group["group_mass"] == pytest.approx(0.98, abs=1e-6)
    assert amstaff["group_score"] == pytest.approx(
        0.08 / 0.98 * 100, abs=1e-3)
    # the top-K scores stay untouched
    assert group["top1_breed"] == SBT
    assert group["top1_confidence"] == 0.40


def test_group_scores_still_sum_to_100_with_full_vector():
    predictions = _predictions(
        (SBT, 0.40), (AMBULL, 0.30), (APBT, 0.20))
    probabilities = {APBT: 0.20, SBT: 0.40, AMBULL: 0.30, AMSTAFF: 0.08,
                     "beagle": 0.02}
    group = build_candidate_group(predictions, class_names=FULL_CLASSES,
                                  probabilities=probabilities)
    assert sum(item["group_score"]
               for item in group["candidates"]) == pytest.approx(100.0, abs=1e-6)


def test_full_vector_does_not_override_missing_classes():
    """Only classes present in ``class_names`` may enter the group."""
    predictions = _predictions((SBT, 0.40), (AMBULL, 0.30))
    probabilities = {SBT: 0.40, AMBULL: 0.30, AMSTAFF: 0.20, "ghost": 0.10}
    group = build_candidate_group(predictions, class_names=FULL_CLASSES,
                                  probabilities=probabilities)
    assert "ghost" not in {item["breed"] for item in group["candidates"]}


def test_full_vector_and_topk_disagree_prefers_full_vector():
    predictions = _predictions((SBT, 0.40), (AMBULL, 0.30))
    probabilities = {SBT: 0.40, AMBULL: 0.30, AMSTAFF: 0.25}
    group = build_candidate_group(predictions, class_names=FULL_CLASSES,
                                  probabilities=probabilities)
    amstaff = next(item for item in group["candidates"]
                   if item["breed"] == AMSTAFF)
    assert amstaff["original_confidence"] == pytest.approx(0.25, abs=1e-6)


def test_empty_probabilities_dict_falls_back_to_topk():
    predictions = _predictions((SBT, 0.40), (AMBULL, 0.30))
    group = build_candidate_group(predictions, class_names=FULL_CLASSES,
                                  probabilities={})
    amstaff = next(item for item in group["candidates"]
                   if item["breed"] == AMSTAFF)
    assert amstaff["original_confidence"] == 0.0


# ---------------------------------------------------------------------------
# 6. a 37-class space without AmStaff must not raise
# ---------------------------------------------------------------------------

def test_v11_class_space_without_amstaff_returns_none():
    """V1.1（37 类）缺 AmStaff：候选组不完整，必须完全退回原有行为。"""
    predictions = _predictions((AMBULL, 0.60), (SBT, 0.20), ("beagle", 0.10))
    group = build_candidate_group(predictions, class_names=V11_CLASSES)
    assert group is None


def test_v11_class_space_with_single_candidate_returns_none():
    classes = [AMBULL, "beagle", "boxer"]
    predictions = _predictions((AMBULL, 0.60), ("beagle", 0.20))
    assert build_candidate_group(predictions, class_names=classes) is None


def test_v11_resolve_entry_point_returns_none():
    """路由入口在 V1.1 类别空间下同样安全返回 None，不抛错。"""
    result = {"predictions": _predictions(
        (AMBULL, 0.60), (SBT, 0.20), ("beagle", 0.10))}
    assert resolve_candidate_group(result, class_names=V11_CLASSES,
                                   enabled=True) is None


def test_v11_class_space_with_no_candidate_returns_none():
    classes = ["beagle", "boxer", "chihuahua"]
    predictions = _predictions(("beagle", 0.60), ("boxer", 0.20))
    assert build_candidate_group(predictions, class_names=classes) is None


def test_unknown_labels_do_not_raise():
    predictions = _predictions(("unknown_breed", 0.60), (AMBULL, 0.20))
    group = build_candidate_group(predictions, class_names=FULL_CLASSES)
    assert group is not None
    assert group["triggered"] is False


# ---------------------------------------------------------------------------
# edge cases: empty / malformed input
# ---------------------------------------------------------------------------

def test_empty_predictions_returns_none():
    assert build_candidate_group([], class_names=FULL_CLASSES) is None


def test_none_class_names_assumes_full_group():
    group = build_candidate_group(_ambiguous_group(), class_names=None)
    assert group is not None
    assert set(group["available_candidates"]) == set(CANDIDATE_GROUP)


def test_group_with_zero_mass_is_not_triggered():
    """Top-1 是 APBT（在组内）但其余三类均无概率时，组内质量不足不触发。"""
    predictions = _predictions((APBT, 0.60), ("beagle", 0.30))
    group = build_candidate_group(predictions, class_names=FULL_CLASSES)
    assert group is not None
    assert group["triggered"] is False
    # APBT 自身概率计入 group_mass（0.60），不触发是因为分差 0.60 > 0.40
    assert group["group_mass"] == pytest.approx(0.60, abs=1e-6)
    assert "分差" in group["reason"]
    # scores stay well-defined even with no other mass
    assert sum(item["group_score"]
               for item in group["candidates"]) == pytest.approx(100.0, abs=0.01)


def test_group_with_truly_zero_mass_is_not_triggered():
    """Top-1 在组外且四类概率全无时，组内质量为 0 且不触发。"""
    predictions = _predictions(("beagle", 0.60), (APBT, 0.0))
    group = build_candidate_group(predictions, class_names=FULL_CLASSES)
    assert group is not None
    assert group["triggered"] is False
    assert group["group_mass"] == 0.0
    assert group["reason"] == "top-1 不在候选组内"
    assert sum(item["group_score"]
               for item in group["candidates"]) == pytest.approx(100.0, abs=0.01)


def test_injected_thresholds_are_honoured():
    predictions = _predictions(
        (AMSTAFF, 0.30), (SBT, 0.28), (AMBULL, 0.25), (APBT, 0.10))
    strict = build_candidate_group(predictions, class_names=FULL_CLASSES,
                                   mass_threshold=0.95,
                                   margin_threshold=0.01)
    assert strict["triggered"] is False
    loose = build_candidate_group(predictions, class_names=FULL_CLASSES,
                                  mass_threshold=0.10,
                                  margin_threshold=0.50)
    assert loose["triggered"] is True


# ---------------------------------------------------------------------------
# 7. the feature switch and the user-selection contract
# ---------------------------------------------------------------------------

def test_resolve_candidate_group_disabled_returns_none():
    result = {"predictions": _ambiguous_group()}
    assert resolve_candidate_group(result, class_names=FULL_CLASSES,
                                   enabled=False) is None


def test_resolve_candidate_group_enabled_computes_group():
    result = {"predictions": _ambiguous_group()}
    group = resolve_candidate_group(result, class_names=FULL_CLASSES,
                                    enabled=True)
    assert group is not None
    assert group["triggered"] is True


def test_resolve_candidate_group_tolerates_missing_predictions():
    assert resolve_candidate_group({}, class_names=FULL_CLASSES,
                                   enabled=True) is None
    assert resolve_candidate_group(None, class_names=FULL_CLASSES,
                                   enabled=True) is None


def test_user_selection_does_not_touch_the_model_prediction():
    """The UI stores a user choice separately; the model payload is immutable."""
    result = {"predictions": _ambiguous_group()}
    group = build_candidate_group(result["predictions"],
                                  class_names=FULL_CLASSES)
    # simulate the front end recording a user pick
    user_choice = SBT
    assert user_choice != group["top1_breed"]
    assert group["top1_breed"] == AMSTAFF          # unchanged
    assert group["top1_confidence"] == 0.34         # unchanged
    assert result["predictions"][0]["breed"] == AMSTAFF
    assert result["predictions"][0]["confidence"] == 0.34


def test_candidate_group_schema_accepts_payload():
    group = build_candidate_group(_ambiguous_group(), class_names=FULL_CLASSES)
    parsed = CandidateGroupInfo(**group)
    assert parsed.triggered is True
    assert len(parsed.candidates) == 4
    assert {item.breed for item in parsed.candidates} == set(CANDIDATE_GROUP)
    assert parsed.threshold_version == "val-2026-10-19-four-breed-b1"


def test_predict_response_candidate_group_defaults_to_none():
    """A legacy-shaped response must still validate (backwards compatible)."""
    response = PredictResponse(
        record_id=1,
        predictions=[{"breed": "beagle", "confidence": 0.9}],
        elapsed_ms=1.0, inference_ms=0.5, preprocess_ms=0.5,
        top_k=3, num_classes=37)
    assert response.candidate_group is None
    assert response.predictions[0].breed == "beagle"


def test_predict_response_accepts_candidate_group():
    group = build_candidate_group(_ambiguous_group(), class_names=FULL_CLASSES)
    response = PredictResponse(
        record_id=1,
        predictions=_ambiguous_group(),
        candidate_group=group,
        elapsed_ms=1.0, inference_ms=0.5, preprocess_ms=0.5,
        top_k=3, num_classes=136)
    assert response.candidate_group.triggered is True


# ---------------------------------------------------------------------------
# 8. the feature flag in Settings
# ---------------------------------------------------------------------------

def test_settings_candidate_group_flag_defaults_to_true():
    """U5.5：四类候选组已随 V2.1 一起成为默认开启的能力。"""
    from backend.app.config import Settings

    assert Settings().candidate_group_enabled is True


def test_settings_candidate_group_flag_can_be_disabled():
    from backend.app.config import Settings

    assert Settings(candidate_group_enabled=False).candidate_group_enabled is False


def test_settings_default_model_is_exp06():
    """U6.6：默认推理模型切换为 exp06（V2.2 候选，136 类，256 分辨率）。

    这里只断言**有判别力**的条件（目录名、分辨率、文件真实存在），
    不写 ``settings.weights_path == DEFAULT_MODEL_DIR / "best_model.pth"``
    这种自洽命题——那种断言在目录写错时依然成立。
    """
    from backend.app.config import (
        DEFAULT_CLASS_NAMES_PATH,
        DEFAULT_IMAGE_SIZE,
        DEFAULT_MODEL_DIR,
        Settings,
    )

    settings = Settings()
    assert DEFAULT_MODEL_DIR.name == (
        "v2_2_border_collie_exp06_resolution256_lowlr_seed42")
    assert settings.weights_path == DEFAULT_MODEL_DIR / "best_model.pth"
    assert settings.weights_path.exists()
    # exp06 训练于 256；分辨率必须与权重配对，否则预处理与训练不匹配
    assert DEFAULT_IMAGE_SIZE == 256
    assert settings.image_size == 256
    # 类别映射继续使用既有那份 136 类表，不为新权重复制/重写
    assert settings.class_names_path == DEFAULT_CLASS_NAMES_PATH
    assert settings.class_names_path.name == "class_names.json"
    assert settings.class_names_path.parent.name == "v2_1_136classes_seed42"
    assert settings.class_names_path.exists()
    # exp06 checkpoint 的 class_names 与该映射逐项一致（内容级核对）
    assert (DEFAULT_MODEL_DIR / "class_names.json").read_bytes() == \
        settings.class_names_path.read_bytes()


def test_settings_image_size_env_override():
    """回退到 224 训练的模型时必须能改回 224（CATDOG_IMAGE_SIZE）。"""
    from backend.app.config import Settings

    assert Settings().image_size == 256
    monkey = {"CATDOG_IMAGE_SIZE": "224"}
    import os

    old = os.environ.get("CATDOG_IMAGE_SIZE")
    try:
        os.environ["CATDOG_IMAGE_SIZE"] = monkey["CATDOG_IMAGE_SIZE"]
        assert Settings.from_env().image_size == 224
        os.environ["CATDOG_IMAGE_SIZE"] = "not-a-number"
        # 非法值回退默认，不得崩溃
        assert Settings.from_env().image_size == 256
    finally:
        if old is None:
            os.environ.pop("CATDOG_IMAGE_SIZE", None)
        else:
            os.environ["CATDOG_IMAGE_SIZE"] = old


def test_settings_v1_1_files_still_exist_untouched():
    """回退目标必须仍然存在（V1.1 与 V2.1 文件不得被覆盖或删除）。"""
    from ml.config import ARTIFACTS_DIR

    assert (ARTIFACTS_DIR / "best_model.pth").exists()
    assert (ARTIFACTS_DIR / "class_names.json").exists()
    assert (ARTIFACTS_DIR / "v2_1_136classes_seed42" / "best_model.pth").exists()
    assert (ARTIFACTS_DIR / "v2_1_136classes_seed42"
            / "class_names.json").exists()
    # exp06 权重本身也不得被覆盖
    assert (ARTIFACTS_DIR
            / "v2_2_border_collie_exp06_resolution256_lowlr_seed42"
            / "best_model.pth").exists()


def test_v2_1_rollback_path_is_still_resolvable(monkeypatch):
    """U6.6：切到 exp06 之后，V2.1 仍是可用的回退目标。

    回退只需两个环境变量（外加把分辨率改回 224），不要求改动任何代码或文件。
    """
    from backend.app.config import Settings
    from ml.config import ARTIFACTS_DIR

    v21 = ARTIFACTS_DIR / "v2_1_136classes_seed42"
    monkeypatch.setenv("CATDOG_WEIGHTS_PATH", str(v21 / "best_model.pth"))
    monkeypatch.setenv("CATDOG_CLASS_NAMES_PATH", str(v21 / "class_names.json"))
    monkeypatch.setenv("CATDOG_IMAGE_SIZE", "224")

    rollback = Settings.from_env()
    assert rollback.weights_path == v21 / "best_model.pth"
    assert rollback.class_names_path == v21 / "class_names.json"
    assert rollback.image_size == 224
    assert rollback.weights_path.exists()
    assert rollback.class_names_path.exists()


def test_env_can_override_model_paths_independently(monkeypatch, tmp_path):
    """回退/切换依赖这两个环境变量，必须真实生效。"""
    from backend.app.config import Settings

    weights = tmp_path / "w" / "best_model.pth"
    names = tmp_path / "n" / "class_names.json"
    monkeypatch.setenv("CATDOG_WEIGHTS_PATH", str(weights))
    monkeypatch.setenv("CATDOG_CLASS_NAMES_PATH", str(names))

    settings = Settings.from_env()
    assert settings.weights_path == weights
    assert settings.class_names_path == names


def test_env_flag_parsing(monkeypatch):
    """显式 false 必须能关闭候选功能；无法识别的值回退到默认（True）。"""
    from backend.app.config import Settings

    monkeypatch.setenv("CATDOG_CANDIDATE_GROUP_ENABLED", "true")
    assert Settings.from_env().candidate_group_enabled is True
    monkeypatch.setenv("CATDOG_CANDIDATE_GROUP_ENABLED", "false")
    assert Settings.from_env().candidate_group_enabled is False
    monkeypatch.setenv("CATDOG_CANDIDATE_GROUP_ENABLED", "0")
    assert Settings.from_env().candidate_group_enabled is False
    # 无法识别的值 → 回退到**当前默认值**（U5.5 起为 True）
    monkeypatch.setenv("CATDOG_CANDIDATE_GROUP_ENABLED", "garbage")
    assert Settings.from_env().candidate_group_enabled is True
