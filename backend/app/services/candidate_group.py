"""相近犬种候选组（APBT / AmStaff / SBT / American Bulldog）判断与组内相对得分。

设计目标：

* **纯函数、可单测、不依赖模型**。输入是 ``ml.predict`` 已经算好的 Top-K
  ``predictions``（原始 softmax，未被篡改）与可选的完整概率向量 ``probabilities``；
* **不篡改任何概率**。传入的 ``predictions`` 数组在函数内既不被排序也不被
  修改，组内相对得分只是另算的归一化值；
* **V1.1 缺类安全**。模型类别空间不包含候选组全部四个标签（37 类同时缺 APBT
  与 AmStaff）时直接返回 ``None``，自然退回原有行为，不抛错；
* **阈值只来自 validation split**（见 ``scripts/evaluate_apbt_four_group.py``
  与 ``reports/v2_1_apbt_four_breed_candidate_eval/``），test split 不参与调参。

组内相对得分::

    group_score_i = p_i / sum(p_j for j in candidate_group) * 100

它**只在四个候选之间归一化**，不是整体识别置信度、真实概率或准确率。
"""
from __future__ import annotations

#: 候选组的 canonical label（U5.2 方案 B1：由三类扩展为四类，新增 APBT）。
#: 成员固定，不得因评估结果随意增删。
CANDIDATE_GROUP: tuple[str, ...] = (
    "american_pit_bull_terrier",
    "american_staffordshire_terrier",
    "staffordshire_bull_terrier",
    "american_bulldog",
)

#: 候选组中文展示名（前端另有一份显示映射，此处供 API 直接返回中文名）。
CANDIDATE_GROUP_ZH: dict[str, str] = {
    "american_pit_bull_terrier": "美国比特斗牛梗",
    "american_staffordshire_terrier": "美国斯塔福郡梗",
    "staffordshire_bull_terrier": "斯塔福郡斗牛梗",
    "american_bulldog": "美国斗牛犬",
}

#: 触发阈值版本标识，沿用既有 ``val-<日期>-<后缀>`` 格式。
#: ``four-breed-b1`` = U5.1 validation-only 离线评估的方案 B1（四类候选组，
#: 沿用 0.30 / 0.40 阈值）。**修改候选组成员或阈值必须同步提升该版本号**，
#: 并在实施报告中记录依据。
THRESHOLD_VERSION = "val-2026-10-19-four-breed-b1"

#: 组内总质量下限：四个候选的原始概率之和至少达到该值，才认为"模型真的在
#: 这几个品种之间做选择"，避免 top-1 偶然落入组内就展示强烈提示。
#: 阈值来源：U5.1 validation-only 离线评估
#: （``reports/v2_1_apbt_four_breed_candidate_eval/evaluation_report.md``），
#: 该评估结论为"沿用 B1 的 0.30 / 0.40，不重新调参"。
MASS_THRESHOLD = 0.30

#: 组内歧义上限：组内第一名与第二名的原始概率差不超过该值，才认为"难以区分"。
#: 阈值来源同上：margin 放宽到 0.50 以上已无法表达"模型难以区分"且不构成
#: 帕累托改进，故维持 0.40。
MARGIN_THRESHOLD = 0.40

#: 组内得分小数位。
_SCORE_DIGITS = 4

# ---------------------------------------------------------------------------
# U6.2：柯利牧羊犬 / 边境牧羊犬双候选提示（与四类组**完全独立**的第二套策略）
# ---------------------------------------------------------------------------
#: 设计目标：当 V2.1 对这两类确实难以区分时，如实展示两个候选让用户自行判断，
#: 而不是强迫模型给出看似确定的单一细粒度品种。
#:
#: * 两个标签仍是**独立模型类别**，不合并标签、不改 checkpoint。
#: * **不因毛色为黑白就触发**：自动毛色启发式与人工复核备注只用于离线分析，
#:   不作为运行时触发条件。
#: * **不硬编码 50/50**：组内得分严格等于 ``p_i / pair_mass * 100``。
#: * 阈值只来自 validation split 的网格扫描（见
#:   ``scripts/u6_2_collie_pair_threshold.py`` 与
#:   ``reports/u6_2_collie_pair_candidate/``），test split 不参与调参。
#: * 版本号与四类组 ``val-2026-10-19-four-breed-b1`` **明确区分**。
COLLIE_PAIR_GROUP: tuple[str, ...] = ("collie", "border_collie")

#: 双候选组中文展示名（两类均已在 136 类中文映射中，此处供 API 直接返回）。
COLLIE_PAIR_GROUP_ZH: dict[str, str] = {
    "collie": "柯利牧羊犬",
    "border_collie": "边境牧羊犬",
}

#: 双候选组阈值版本标识，沿用 ``val-<日期>-<后缀>`` 格式，但与四类组区分。
#:
#: v2（U6.7）：判定量由"绝对分差"改为"组内相对份额"。
#: v1 用的是 ``abs(p_collie - p_border_collie) <= 0.30``，该量源自 softmax 的
#: **绝对值**，会随模型整体置信度漂移：切换到更果断的 exp06 后，31 张目标类图
#: 的绝对分差最小也达 0.3281，策略因此永久休眠（全量 2079 张验证集触发 0 张）。
COLLIE_PAIR_VERSION = "val-2026-10-21-collie-pair-v2"

#: 组内总质量下限：两类原始概率之和至少达到该值，才认为"模型真的在这两个
#: 品种之间做选择"。取 0.30 与四类组门槛保持一致；该值不是本策略的判别主力
#: （见下方 share 阈值的说明）。
COLLIE_PAIR_MASS_THRESHOLD = 0.30

#: **组内相对份额**阈值：``share = min(p_collie, p_border_collie) / pair_mass``，
#: 即较弱一方在两类的相对占比。share >= 该值才认为"两类难以区分"。
#:
#: 为什么用 share 而不是绝对分差：share 与 softmax 的绝对尺度无关。同一批图片在
#: V2.1 与 exp06 下 share 几乎不变（三张已知歧义图分别为 39.9%/39.6%/27.8% 与
#: 29.6%/24.3%/20.6%），而绝对分差会整体漂移（0.20 vs 0.41）。
#:
#: 0.20 的来历（validation 2079 张，规则在看数据前已写定）：
#:   * 覆盖：v1 曾触发的 3 张图在 exp06 下 share 为 0.2962 / 0.2430 / 0.2058，
#:     取 >= 0.20 才能全部覆盖；取 0.25 只剩 1 张，不满足覆盖要求。
#:   * 安全：0.20 时触发 3 张、真实标签全在组内、**组外误触发 0**；
#:     0.10 会多纳入 3 张 share≈0.10~0.11 的图，无明显收益且更宽松。
#:   * 间隔：目标类中次高的 share 仅 0.1119，与 0.2058 之间有约 1.84 倍间隔。
#: 注意：该阈值由 validation 选出，因此同一 validation 的结果**不能**再被当作
#: 独立的无偏泛化估计。
COLLIE_PAIR_SHARE_THRESHOLD = 0.20

#: 候选组标识，供前端与 API 客户端区分两套并行策略。
GROUP_ID_FOUR_BREED = "four-breed-bully"
GROUP_ID_COLLIE_PAIR = "collie-pair"


def _pair_normalised_scores(values: list[float], mass: float) -> list[float]:
    """双候选组内相对得分（百分比），与四类组同样的 drift 补齐约定。

    逐项四舍五入会出现 99.9999 这类总数；把漂移补到第一项上，
    既保持总和为 100，又把误差控制在不影响阅读的量级。
    """
    if mass <= 0:
        scores = [100.0 / len(values)] * len(values)
    else:
        scores = [value / mass * 100 for value in values]
    rounded = [round(value, _SCORE_DIGITS) for value in scores]
    drift = round(100.0 - sum(rounded), _SCORE_DIGITS)
    if drift and len(rounded) > 1:
        rounded[0] = round(rounded[0] + drift, _SCORE_DIGITS)
    return rounded


def build_candidate_group(
    predictions: list[dict],
    class_names: list[str] | None = None,
    mass_threshold: float = MASS_THRESHOLD,
    margin_threshold: float = MARGIN_THRESHOLD,
    probabilities: dict[str, float] | None = None,
) -> dict | None:
    """根据原始 Top-K 预测构造候选组信息；不满足条件返回 ``None``。

    参数
    ----
    predictions:
        ``ml.predict.predict_from_tensor`` 的输出，元素形如
        ``{"breed": str, "confidence": float}``，按分数降序。
    class_names:
        模型完整类别空间。``None`` 时假定候选组全部可用（测试/调用方已确认）。
        传入不含 AmStaff 的 37 类列表时，候选组只保留实际存在的标签。
    mass_threshold / margin_threshold:
        触发阈值，默认取模块常量；测试可注入以覆盖分支。
    probabilities:
        可选的**完整 softmax 向量**（``{类别: 分数}``，由
        ``ml.predict.predict_from_tensor`` 提供）。提供时，候选概率以它为准；
        未提供（例如只有 Top-K 的旧调用方）则退回从 ``predictions`` 读取，
        此时排名低于 ``top_k`` 的候选会被当作 0 分——这正是要避免的情况。

    返回
    ----
    ``None`` 或包含以下键的 dict::

        {
          "triggered": bool,
          "threshold_version": str,
          "top1_breed": str,                 # 模型原始 top-1
          "top1_confidence": float,          # 模型原始 top-1 概率（未篡改）
          "candidates": [...],               # 固定四项，按组内得分降序
          "available_candidates": [...],     # 当前模型类别空间中存在的候选
          "group_mass": float,               # 组内原始概率之和
          "group_margin": float,             # 组内 top1 - top2 原始概率差
          "reason": str,                     # 触发/不触发的原因（人类可读）
        }

    保证：**不修改传入的 ``predictions`` 列表或其元素**。
    """
    if not predictions:
        return None

    # 原始概率查找表。优先使用完整 softmax 向量，避免候选因排在 top_k
    # 之后而被误判为 0 分（那会让 UI 显示"0%"从而歪曲模型输出）。
    original: dict[str, float] = {}
    for item in predictions:
        breed = item.get("breed")
        if not breed:
            continue
        original.setdefault(breed, float(item.get("confidence", 0.0) or 0.0))
    if probabilities:
        for breed, score in probabilities.items():
            original.setdefault(breed, float(score or 0.0))

    top1_breed = predictions[0].get("breed")
    top1_confidence = float(predictions[0].get("confidence", 0.0) or 0.0)

    # 候选组在当前模型类别空间中的可用子集。业务定义固定为四个品种，
    # 缺任何一个（例如 37 类模型没有 AmStaff）就不构成"候选组"，
    # 直接返回 None 保持原有行为。
    if class_names is None:
        available = list(CANDIDATE_GROUP)
    else:
        known = set(class_names)
        available = [label for label in CANDIDATE_GROUP if label in known]
    if len(available) < len(CANDIDATE_GROUP):
        return None

    # 候选组内各项的原始概率。某个候选可能不在 Top-K 里，此时其原始概率
    # 未知（按 0 处理），该情况会在 reason 中说明。
    candidate_probs = {label: original.get(label, 0.0) for label in available}
    group_mass = sum(candidate_probs.values())
    ranked = sorted(candidate_probs.items(), key=lambda kv: -kv[1])
    group_top1 = ranked[0][1]
    group_top2 = ranked[1][1] if len(ranked) > 1 else 0.0
    group_margin = group_top1 - group_top2

    def _normalised_scores(probabilities: list[float]) -> list[float]:
        """组内相对得分（百分比），并保证展示值之和精确等于 100。

        逐项四舍五入会出现 99.9999 这类总数；把漂移补到最大项上，
        既保持总和为 100，又把误差控制在不影响阅读的量级。
        """
        if group_mass <= 0:
            scores = [100.0 / len(probabilities)] * len(probabilities)
        else:
            scores = [value / group_mass * 100 for value in probabilities]
        rounded = [round(value, _SCORE_DIGITS) for value in scores]
        drift = round(100.0 - sum(rounded), _SCORE_DIGITS)
        if drift and len(rounded) > 1:
            rounded[0] = round(rounded[0] + drift, _SCORE_DIGITS)
        return rounded

    group_scores = _normalised_scores([value for _, value in ranked])
    candidates = [
        {
            "breed": label,
            "breed_zh": CANDIDATE_GROUP_ZH.get(label, label),
            "original_confidence": round(probability, 6),
            "group_score": score,
        }
        for (label, probability), score in zip(ranked, group_scores)
    ]

    triggered = (
        top1_breed in available
        and group_mass >= mass_threshold
        and group_margin <= margin_threshold
    )

    if top1_breed not in available:
        reason = "top-1 不在候选组内"
    elif group_mass < mass_threshold:
        reason = (f"候选组总概率 {group_mass:.4f} 低于阈值 "
                  f"{mass_threshold:.2f}，模型未在这几个品种间做选择")
    elif group_margin > margin_threshold:
        reason = (f"组内分差 {group_margin:.4f} 大于阈值 "
                  f"{margin_threshold:.2f}，模型已有明确偏好")
    else:
        reason = (f"top-1 在候选组内、组内总概率 {group_mass:.4f} ≥ "
                  f"{mass_threshold:.2f} 且组内分差 {group_margin:.4f} ≤ "
                  f"{margin_threshold:.2f}")

    return {
        "group_id": GROUP_ID_FOUR_BREED,
        "triggered": triggered,
        "threshold_version": THRESHOLD_VERSION,
        "top1_breed": top1_breed,
        "top1_confidence": round(top1_confidence, 6),
        "candidates": candidates,
        "available_candidates": available,
        "group_mass": round(group_mass, 6),
        "group_margin": round(group_margin, 6),
        "reason": reason,
    }


def build_collie_pair_group(
    predictions: list[dict],
    class_names: list[str] | None = None,
    mass_threshold: float = COLLIE_PAIR_MASS_THRESHOLD,
    share_threshold: float = COLLIE_PAIR_SHARE_THRESHOLD,
    probabilities: dict[str, float] | None = None,
) -> dict | None:
    """柯利牧羊犬 / 边境牧羊犬双候选提示；不满足条件返回 ``None``。

    与 :func:`build_candidate_group` 共享同一套设计约定，但**成员、阈值、
    版本完全独立**，互不影响：

    * 完整 softmax 优先（``probabilities`` 提供时以它为准，未提供退回 Top-K）；
    * 两类都必须存在于 ``class_names``，否则返回 ``None``
      （V1.1 的 37 类空间不含这两类，因此自然安全退回）；
    * 组内得分 ``p_i / pair_mass * 100`` 并带 drift 补齐保证和 = 100，
      **不硬编码 50/50**；
    * **不修改传入的 ``predictions`` 列表或其元素**。

    触发条件（三者同时满足）：

    1. 原始 Top-1 属于 :data:`COLLIE_PAIR_GROUP`；
    2. ``pair_mass = p_collie + p_border_collie >= mass_threshold``；
    3. ``share = min(p_collie, p_border_collie) / pair_mass >= share_threshold``
       —— **组内相对份额**，与 softmax 绝对尺度无关（v2 起取代 v1 的绝对分差）。

    Top-1 是其它品种时返回 ``None``——即使这两类彼此接近，也不暗示图片一定
    属于其中之一。
    """
    if not predictions:
        return None

    if class_names is not None:
        available = [label for label in COLLIE_PAIR_GROUP
                     if label in set(class_names)]
        if len(available) != len(COLLIE_PAIR_GROUP):
            return None
    else:
        available = list(COLLIE_PAIR_GROUP)

    top1 = predictions[0].get("breed")
    if top1 not in COLLIE_PAIR_GROUP:
        return None

    # 原始概率查找表（只读副本，不触碰调用方数据）。
    original: dict[str, float] = {}
    for item in predictions:
        breed = item.get("breed")
        if not breed:
            continue
        original.setdefault(breed, float(item.get("confidence", 0.0) or 0.0))
    if probabilities:
        for breed, score in probabilities.items():
            original.setdefault(breed, float(score or 0.0))

    pair_mass = sum(original.get(label, 0.0) for label in COLLIE_PAIR_GROUP)
    pair_margin = abs(original.get("collie", 0.0)
                      - original.get("border_collie", 0.0))
    # 组内相对份额：较弱一方在两类的占比。与 softmax 绝对尺度无关，
    # 因此不会因为模型整体更果断就永久失效（这正是 v1 绝对分差的问题）。
    pair_share = (min(original.get("collie", 0.0),
                      original.get("border_collie", 0.0)) / pair_mass
                  if pair_mass > 0 else 0.0)

    triggered = (pair_mass >= mass_threshold
                 and pair_share >= share_threshold)
    if triggered:
        reason = (f"top-1 在候选组内、组内总概率 {pair_mass:.4f} >= "
                  f"{mass_threshold:.2f} 且组内相对份额 {pair_share:.4f} >= "
                  f"{share_threshold:.2f}")
    elif pair_mass < mass_threshold:
        reason = (f"组内总概率 {pair_mass:.4f} < {mass_threshold:.2f}，"
                  f"模型未在这两个品种之间做选择")
    else:
        reason = (f"组内相对份额 {pair_share:.4f} < {share_threshold:.2f}，"
                  f"模型已在这两个品种之间做出明确偏好")

    scores = _pair_normalised_scores(
        [original.get(label, 0.0) for label in COLLIE_PAIR_GROUP], pair_mass)
    candidates = [{
        "breed": label,
        "breed_zh": COLLIE_PAIR_GROUP_ZH[label],
        "original_confidence": original.get(label, 0.0),
        "group_score": scores[index],
    } for index, label in enumerate(COLLIE_PAIR_GROUP)]
    candidates.sort(key=lambda item: (-item["group_score"],
                                      item["breed"]))

    return {
        "group_id": GROUP_ID_COLLIE_PAIR,
        "triggered": triggered,
        "threshold_version": COLLIE_PAIR_VERSION,
        "top1_breed": top1,
        "top1_confidence": float(predictions[0].get("confidence", 0.0) or 0.0),
        "candidates": candidates,
        "available_candidates": available,
        "group_mass": round(pair_mass, 6),
        "group_margin": round(pair_margin, 6),
        #: v2 起真正决定是否触发的量；group_margin 仅作信息性字段保留。
        "group_share": round(pair_share, 6),
        "reason": reason,
    }


def resolve_candidate_group(
    result: dict,
    class_names: list[str] | None = None,
    enabled: bool = False,
) -> dict | None:
    """路由层入口：仅在显式启用时计算候选组，否则原样返回旧行为。

    ``result`` 是 ``Predictor.predict_pil`` 的输出（含 ``predictions``，以及
    可选的完整 softmax 向量 ``probabilities``）。``enabled`` 为 ``False`` 时
    直接返回 ``None``——响应字段集合与 V1.1 一致（两套策略都关闭）。

    策略按**原始 Top-1** 分发，两套候选组互不干扰：

    * Top-1 属于四类 bully 组 → :func:`build_candidate_group`（既有逻辑）；
    * Top-1 属于 :data:`COLLIE_PAIR_GROUP` → :func:`build_collie_pair_group`；
    * 其它 Top-1 → ``None``（不展示任何候选）。
    """
    if not enabled:
        return None
    predictions = (result or {}).get("predictions") or []
    if not predictions:
        return None

    top1 = predictions[0].get("breed")
    probabilities = (result or {}).get("probabilities")

    if top1 in COLLIE_PAIR_GROUP:
        return build_collie_pair_group(
            predictions, class_names=class_names,
            probabilities=probabilities)
    return build_candidate_group(
        predictions, class_names=class_names,
        probabilities=probabilities)
