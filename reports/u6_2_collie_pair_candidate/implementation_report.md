# U6.2：柯利牧羊犬 / 边境牧羊犬双候选提示 — 实现报告

> **策略标识**：`collie-pair`　**阈值版本**：`val-2026-10-21-collie-pair-v1`
> **正式默认模型**：仍为 V2.1（136 类），未切换
> **既有四类候选组**：成员、阈值（mass 0.30 / margin 0.40）、版本
> （`val-2026-10-19-four-breed-b1`）与触发行为**完全未改**
> **评估集**：`data/v2_processed/val`（2,079 张）；**test split 访问次数 = 0**
> **生成时间**：2026-10-21

---

## 1. 目标与实现摘要

当 V2.1 对 `collie`（柯利牧羊犬）与 `border_collie`（边境牧羊犬）确实难以区分时，
如实展示两个候选及「候选组内相对得分」，让用户自行判断；不强迫模型给出看似确定的
单一细粒度品种。

实现方式是在 `backend/app/services/candidate_group.py` 中新增一套**与四类 bully
候选组完全平行、互不干扰**的策略，由 `resolve_candidate_group` 按**原始 Top-1**
分发；响应新增可选字段 `group_id` 用于区分两套策略。

**两个标签仍是独立模型类别**：未合并标签、未改 checkpoint、未训练。

---

## 2. 触发定义（三者同时满足）

```
Top-1 ∈ {collie, border_collie}
且 pair_mass   = p_collie + p_border_collie          >= 0.30
且 pair_margin = abs(p_collie - p_border_collie)     <= 0.30
```

- **必须使用完整 136 维 Softmax**，不得从 Top-K 截断值推算
  （`ml.predict.predict_from_tensor` 已透传内部 `probabilities` 字段）。
- Top-1 是其它品种时返回 `None`——即使这两类彼此接近，也不暗示图片一定属于其中之一。
- **不因毛色为黑白就触发**：自动毛色启发式与人工复核备注只用于离线分析，
  不作为运行时触发条件。
- **不硬编码 50/50**：`group_score_i = p_i / pair_mass * 100`。

---

## 3. 阈值选择依据（validation 网格扫描）

### 3.1 扫描设置

- 脚本：`scripts/u6_2_collie_pair_threshold.py`（只读 V2.1，一次前向）
- 网格：`mass ∈ {0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50}` ×
  `margin ∈ {0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40}` 共 **56 组合**
- 明细：`validation_threshold_grid.csv`（56 行）、`validation_trigger_samples.csv`（29 行）
- 汇总：`u6_2_frozen_thresholds.json`

### 3.2 选择规则（扫描前写定，保守优先）

1. 触发图中真实标签在组内的比例 **≥ 0.5**；
2. 组外误触发数**最少**；
3. 触发率不超过「Top-1 属两类的子集」的 **50%**（防止"不确定才提示"退化为"总是提示"）；
4. 在零组外误触发的前提下取**最大的 margin 档位**。

> **规则修正说明**：计划原文第 4 条写作「取 margin 最大（最严格）」，该表述方向有误
> ——margin 阈值越大越宽松。按「保守优先、只有难以区分时才提示」的原意，本条实际执行为
> 「在零组外误触发的前提下取最大 margin 档位」。此处如实记录该修正，未静默更改规则。

### 3.3 选择结果

| mass | margin | 触发数 | 组内比例 | 组外误触发 | 组外标签 |
|---:|---:|---:|---:|---:|---|
| 0.10–0.50 | 0.25 | 2 | 1.000 | 0 | — |
| **0.10–0.50** | **0.30** | **3** | **1.000** | **0** | **—** |
| 0.10–0.50 | 0.40 | 4 | 0.750 | 1 | bernese_mountain_dog |

- **mass 在该子集内完全不敏感**：0.10–0.50 在 margin ≤ 0.30 时触发结果一致（3 张）。
  取 0.30 是为与四类组 mass 门槛保持一致，**并非数据表明 0.30 更优**。
- margin ≤ 0.30 是**最后一个零组外误触发**的档位；放宽到 0.40 会引入
  1 张组外误触发（`bernese_mountain_dog`）。

**最终冻结**：`pair_mass ≥ 0.30`、`pair_margin ≤ 0.30`。

### 3.4 冻结阈值下的验证集表现

| 指标 | 值 |
|---|---|
| val 总数 | 2,079 |
| Top-1 属两类的子集 | **29** 张 |
| 真实标签属两类的样本 | 31 张（collie 16 + border_collie 15） |
| **触发数** | **3** 张 |
| 触发率（相对 val 总数） | **0.1443%** |
| 触发率（相对 Top-1 属两类子集） | 10.34% |
| 触发图中真实标签在组内 | **3 / 3 = 100%** |
| 组外误触发 | **0** |
| 真实 `collie` 被提示 | **0 / 16** |
| 真实 `border_collie` 被提示 | **3 / 15** |

---

## 4. 关键发现（必须如实呈现）

**真实 `collie` 的 14 张 Top-1 属两类图片中，`pair_margin` 全部 ≥ 0.7131**
（最小 0.7131，最大 0.9986）。也就是说，**模型对这两类几乎不存在竞争**——
双候选提示实际上只在「真实 `border_collie` 与 `collie` 接近」时触发。

3 张触发图全部是真实 `border_collie`：

| 图片 | 真实标签 | Top-1 | p(Top-1) | p_collie | p_border_collie | mass | margin |
|---|---|---|---:|---:|---:|---:|---:|
| `n02106166_416.jpg` | border_collie | border_collie | 0.6004 | 0.3987 | 0.6004 | 0.9992 | 0.2017 |
| `n02106166_549.jpg` | border_collie | **collie** | 0.6032 | 0.6032 | 0.3954 | 0.9987 | 0.2078 |
| `n02106166_884.jpg` | border_collie | border_collie | 0.4107 | 0.1582 | 0.4107 | 0.5689 | 0.2525 |

其中第 2 张正是「真实边牧被模型判成柯利」的典型混淆案例——双候选提示对这类样本
有直接价值。

---

## 5. 实现细节

### 5.1 后端（`backend/app/services/candidate_group.py`）

新增（四类组常量与 `build_candidate_group` **一行未动**）：

```python
COLLIE_PAIR_GROUP = ("collie", "border_collie")
COLLIE_PAIR_GROUP_ZH = {"collie": "柯利牧羊犬", "border_collie": "边境牧羊犬"}
COLLIE_PAIR_VERSION = "val-2026-10-21-collie-pair-v1"
COLLIE_PAIR_MASS_THRESHOLD = 0.30
COLLIE_PAIR_MARGIN_THRESHOLD = 0.30
GROUP_ID_FOUR_BREED = "four-breed-bully"
GROUP_ID_COLLIE_PAIR = "collie-pair"

def build_collie_pair_group(predictions, class_names=None,
                            mass_threshold=..., margin_threshold=...,
                            probabilities=None) -> dict | None
def _pair_normalised_scores(values, mass) -> list[float]
```

`build_collie_pair_group` 的设计约定与四类组一致：完整概率优先、**要求两类都在
`class_names` 中否则返回 `None`**（V1.1 的 37 类空间不含这两类，因此自然安全退回）、
组内得分带 drift 补齐保证和 = 100、**不修改传入的 `predictions`**。

`resolve_candidate_group` 改为按原始 Top-1 分发：

```python
if top1 in COLLIE_PAIR_GROUP:
    return build_collie_pair_group(...)
return build_candidate_group(...)      # 既有四类逻辑
```

四类组返回值新增 `group_id: "four-breed-bully"`（仅此一行改动，其余行为不变）。

### 5.2 Schema（`backend/app/schemas.py`）

`CandidateGroupInfo` 新增**可选**字段：

```python
group_id: str | None = Field(
    None, description="which candidate strategy produced this group: "
                      "'four-breed-bully' or 'collie-pair'")
```

默认 `None` 保证旧响应与旧消费者兼容（已有单测固化）。
`CandidateBreedItem` 字段不变（`breed/breed_zh/original_confidence/group_score`），
**未新增任何概率向量字段**。

### 5.3 前端（`frontend/src/components/PredictionResult.vue`）

- 候选区头部新增 `group_id` 可见渲染（`.candidate-group-id` +
  `data-group-id` 属性），使「按组标识正确渲染」可被测试断言；
- 新增 `candidateSubtitle` computed：`collie-pair` → 「模型对柯利牧羊犬与边境牧羊犬
  难以明确区分」，其它 → 「模型在这几个品种间难以明确区分」；
- 说明文案补充任务 §3 要求的声明：**「也不保证候选中一定包含正确品种」**；
- 候选数量仍由 `candidateCount` 动态计算（`v-for` 渲染），**未硬编码 3 或 4**；
- 中文名无需新增映射——两类牧羊犬已在 136 条 `BREED_NAMES_ZH` 中。

---

## 6. 用户交互与数据安全

| 要求 | 实现 |
|---|---|
| 原始 Top-1 / Top-K / 分数不变 | 双候选函数不修改传入 `predictions`；单测与 API 验收逐项固化 |
| 分数只展示为「候选组内相对得分」 | 图例文案 + `group_score` 语义；明确声明不是整体识别置信度/真实概率/准确率 |
| 用户选择与模型预测分开显示 | 「你选择的品种」独立区块，文案「模型首选仍为 … 未被替换」 |
| 选择仅存组件状态，不写库 | `userChoice` 为组件 `ref`，无任何 API 调用 |
| 不覆盖历史预测 | DB 表字段仍为 `id/image_path/predicted_breed/confidence/top_k_json/inference_ms/created_at` |
| 关闭开关后两种候选都关闭 | `resolve_candidate_group` 在 `enabled=False` 时直接返回 `None` |
| V1.1 回退安全 | 两类标签不在 37 类空间 → `build_collie_pair_group` 返回 `None`，不抛异常 |

---

## 7. 限制（如实说明）

1. **触发率极低（0.1443%）**：这是"只有难以区分时才提示"的语义结果，不是缺陷。
2. **真实 `collie` 永远不会被提示**（0/16）：模型对真实柯利的 margin 全部 ≥ 0.7131。
   双候选的实际价值在于「真实边牧被误判为柯利」的场景。
3. **小分母**：val 中 collie 仅 16 张、border_collie 仅 15 张；Top-1 属两类子集仅 29 张；
   触发样本仅 3 张。**任何比例都不可外推为总体准确率**。
4. **不宣称提高分类准确率**：本任务只改推理结果的**展示方式**，未训练、未改模型；
   没有证据表明候选提示能提高品种识别准确率。
5. **组外误触发在当前阈值下为 0**，但阈值放宽到 margin 0.40 会出现
   `bernese_mountain_dog` 误触发——这是保守阈值的直接代价（漏掉部分竞争样本）。
6. **mass 阈值未被数据区分**：0.10–0.50 在该子集内等效，取 0.30 只为与四类组一致。

---

## 8. 交付物

| 文件 | 内容 |
|---|---|
| `implementation_report.md` | 本报告 |
| `validation_threshold_grid.csv` | 56 组合的全部统计指标（含分子/分母） |
| `validation_trigger_samples.csv` | 29 张 Top-1 属两类图的逐图概率、pair_mass、pair_margin |
| `u6_2_frozen_thresholds.json` | 冻结阈值、选择规则、证据与小分母警示 |
| `acceptance_report.md` | 自动测试、隔离 API、真实页面验收结果 |
| `acceptance_api_responses.json` | 58 项 API 检查明细与响应证据 |
| `page_acceptance_on.json` / `_off.json` | 页面验收检查明细 |
| `screenshots/01–07*.png` | 7 张全页截图 |
| `protection_snapshot_before.json` / `_after.json` | 保护快照（自动比对一致） |
| `git_status_before.txt` / `git_status_after.txt` | 工作区状态前后副本 |
| `git_diff_stat_before.txt` / `git_diff_check_before.txt` | 差异摘要与空白检查 |

---

## 9. 代码改动清单

### 修改

| 文件 | 改动 |
|---|---|
| `backend/app/services/candidate_group.py` | 新增 `COLLIE_PAIR_*` 六个常量、`_pair_normalised_scores`、`build_collie_pair_group`；`resolve_candidate_group` 改为按 Top-1 分发；四类组返回值新增 `group_id` |
| `backend/app/schemas.py` | `CandidateGroupInfo` 新增可选 `group_id: str \| None = None` |
| `frontend/src/components/PredictionResult.vue` | 候选区头部新增 `group_id` 渲染与 `.candidate-group-id` 样式；新增 `candidateSubtitle` computed；说明文案补充「不保证候选中一定包含正确品种」 |

### 新增

| 文件 | 用途 |
|---|---|
| `scripts/u6_2_collie_pair_threshold.py` | val 单次前向 + 56 组合网格扫描 |
| `scripts/accept_collie_pair_api.py` | 隔离环境 API 验收（58 项） |
| `scripts/page_accept_collie_pair.mjs` | Playwright + 系统 Chrome 页面验收 |
| `tests/test_collie_pair_candidate.py` | 15 个后端单测 |

**未触碰**：`backend/app/routes/predict.py`、`backend/app/services/predictor.py`、
`ml/predict.py`、`ml/predictor.py`、`ml/train.py`、`frontend/src/utils/breedNames.js`、
`artifacts/**`、`data/**`、`data/app.db`、`uploads/`、所有既有报告目录。

---

**已停止，等待人工审核。未训练、未切换模型、未写数据库、未访问 test split、未提交 Git。**
