# U5.2 方案 B1 四类相近犬种候选组 — 实施报告

> **阶段**：U5.2 正式实现（推理结果展示逻辑调整，**非模型训练**）
> **正式模型**：V1.1 `artifacts/best_model.pth`（37 类），**未切换、未改动**
> **候选模型**：V2.1 `artifacts/v2_1_136classes_seed42/`，**仍为独立候选**
> **新报告目录**：`reports/v2_1_four_breed_candidate_implementation/`（未覆盖任何既有报告目录）
> **生成时间**：2026-10-19

---

## 1. 本次实现内容

将相近犬种候选组从**三类**（AmStaff / SBT / American Bulldog）正式扩展为
**四类**（新增 APBT），阈值与算法完全沿用 U5.1 方案 B1。

| 项目 | 改动前（三类） | 改动后（四类 B1） |
|---|---|---|
| `CANDIDATE_GROUP` | AmStaff、SBT、American Bulldog | **+ APBT**（共 4 项） |
| `CANDIDATE_GROUP_ZH` | 3 项中文名 | **+ `美国比特斗牛梗`** |
| `THRESHOLD_VERSION` | `val-2026-10-19-v1` | **`val-2026-10-19-four-breed-b1`** |
| `MASS_THRESHOLD` | 0.30 | **0.30（不变）** |
| `MARGIN_THRESHOLD` | 0.40 | **0.40（不变）** |
| 算法逻辑 | 完整概率优先、成员须齐全、drift 补齐 | **完全不变** |

### 修改/新增文件

| 文件 | 类型 | 内容 |
|---|---|---|
| `backend/app/services/candidate_group.py` | 修改 | `CANDIDATE_GROUP` 扩为四项、`CANDIDATE_GROUP_ZH` 补 APBT 中文名、`THRESHOLD_VERSION` 升级为 `val-2026-10-19-four-breed-b1`、模块 docstring 与 2 处注释由"三个候选"改为"四个候选" |
| `frontend/src/utils/breedNames.js` | 修改 | `CANDIDATE_BREED_NAMES_ZH` 补 APBT、`CANDIDATE_GROUP` 扩为四项；`BREED_MAPPING_SIZE` 仍为 37 |
| `tests/test_candidate_group.py` | 修改 | 三项断言改四项语义；新增 11 个四类专属用例（36 → 52） |
| `frontend/tests/predictionResult.test.js` | 修改 | `radios.length` 3→4、四类中文名断言、新增"不暗示必有正确答案"断言 |
| `frontend/tests/predictionResultAcceptance.test.js` | 修改 | 数据源切换为本次新生成的 `acceptance_api_responses.json`（四类真实响应） |
| `frontend/tests/breedNames.test.js` | 修改 | `CANDIDATE_GROUP` 三项→四项、新增 APBT 中文名断言 |
| `scripts/accept_four_breed_candidate_api.py` | **新增** | 隔离环境四类 API 验收脚本 |
| 本目录 6 个报告文件 | **新增** | 见第 6 节 |

**未修改**：`ml/predict.py`、`ml/predictor.py`、`backend/app/config.py`、
`backend/app/schemas.py`、`backend/app/routes/predict.py`、
`backend/app/services/predictor.py`、`frontend/src/components/PredictionResult.vue`
（候选区本就是 `v-for` 动态渲染，模板无需改动）。

---

## 2. 行为说明

### 2.1 触发规则（四类 B1）

同时满足三条才触发：

1. 模型**原始 Top-1** 属于四类候选组；
2. `group_mass`（完整 Softmax 中四类概率之和）`>= 0.30`；
3. `group_margin`（四类中最高 − 第二高原始概率）`<= 0.40`。

**完整 136 维概率**：U5.1 已修复 Top-K 截断问题，`group_mass` / `group_margin`
与组内得分全部基于 `ml/predict.py` 透传的完整 softmax 向量计算，**不使用
Top-K 截断概率，不把 Top-K 外的候选当作 0**。

### 2.2 组内相对得分

```
group_score_i = p_i / group_mass * 100
```

- 名称明确标注为"**候选组内相对得分**"，**不是**整体识别置信度、真实概率或准确率；
- 实现中对四舍五入漂移做补齐，保证展示值之和**精确等于 100**；
- 同时返回每项的 `original_confidence`（原始 softmax，6 位）供调试追踪。

### 2.3 原始模型结果保留

- 未改 `ml/predict.py` 的原始预测排序、Softmax 概率、Top-K 或 Top-1；
- 响应中 `predictions`（原始 Top-K）与 `candidate_group` **并存**，前者不被后者替换；
- 前端"模型预测"与"你选择的品种"**分区展示**，用户选择仅存组件本地 `ref`，
  不新增 API 写入、不写 SQLite、不改历史记录 schema。

### 2.4 兼容与降级

- `CATDOG_CANDIDATE_GROUP_ENABLED` **默认关闭**；`weights_path` 默认值未动；
- 关闭时响应不含 `candidate_group`，与 V1.1 行为一致；
- V1.1（37 类）同时缺 APBT 与 AmStaff，`build_candidate_group` 直接返回
  `None`，**不抛错**；
- 路由层对候选组计算有 try/except 兜底，计算失败不影响原始预测响应。

---

## 3. 测试结果（实际执行）

| 命令 | 结果 |
|---|---|
| `.venv\Scripts\python.exe -m pytest tests/ -q` | **244 passed**（U5.1 后 233，+11 新增用例） |
| `cd frontend; npm test`（`vitest run`） | **74 passed / 11 files**（U5.1 后 73，+1 新增断言组） |
| `cd frontend; npm run build` | **构建成功**（801 ms；chunk >500 kB 警告为既有情况） |

### 3.1 后端新增用例（11 项，覆盖任务单 4.1 的 10 项要求）

| # | 用例 | 对应任务单要求 |
|---|---|---|
| 1 | `test_four_breed_group_members_are_exact` | ① 四类成员完整且 label 正确 |
| 2 | `test_four_breed_group_has_chinese_names_for_every_member` | ① 中文名齐全 |
| 3 | `test_top1_apbt_triggers_when_thresholds_met` | ④ Top-1 为 APBT 触发；⑦ 与 `predictions[0]` 一致 |
| 4 | `test_top1_apbt_does_not_trigger_when_group_margin_too_large` | ③ 阈值严格遵循 |
| 5 | `test_four_breed_scores_sum_to_100_and_match_normalisation` | ⑥ 得分和≈100 且归一化一致 |
| 6 | `test_four_breed_candidate_outside_topk_uses_real_probability` | ② Top-K 外候选用真实概率 |
| 7 | `test_top1_outside_four_group_with_partial_mass_does_not_trigger` | ⑤ Top-1 组外不触发 |
| 8 | `test_v11_37_class_space_missing_apbt_returns_none` | ⑧ V1.1 不崩溃 |
| 9 | `test_class_space_with_three_of_four_members_returns_none` | ⑧ 缺任一成员安全退回 |
| 10 | `test_group_with_truly_zero_mass_is_not_triggered` | ③ 边界情形 |
| 11 | `test_threshold_version_marks_the_four_breed_b1_strategy` | 版本可追溯 |

（另有既有用例改造：`test_group_mass_and_margin_are_reported`、
`test_not_triggered_when_group_mass_too_low`、
`test_not_triggered_when_both_conditions_fail`、
`test_mass_threshold_boundary_is_inclusive`、
`test_top1_outside_group_is_not_triggered`、
`test_full_probability_vector_is_used_when_provided`、
`test_group_with_zero_mass_is_not_triggered`、
`test_candidate_group_schema_accepts_payload` 等由三项数值改为四项。）

### 3.2 前端新增/更新用例

`predictionResult.test.js`：`radios.length === 4`、四类中文名（含
"美国比特斗牛梗"）、得分和≈100 与"候选组内相对得分"标注、原始 Top-K 不被
替换、用户选择独立且不改 props、未触发/`triggered=false` 不渲染候选区、
**文案不含"其中必有一个 / 必然 / 一定是"**。

`predictionResultAcceptance.test.js`：数据源切换为本次隔离环境真实响应，
覆盖四品种渲染、得分和 100、得分严格等于原始概率归一化、Top-1 不被替换、
用户选择独立、未触发/关闭不渲染、"登记品种"提示与无"必有正确答案"暗示。

---

## 4. 限制与已知问题（如实说明）

1. **触发率不等于模型准确率**。U5.1 validation-only 评估的四类 B1 结果为
   **12 / 2,079 触发（0.58%）**、触发样本组内真实标签覆盖 **8/12**、
   组外触发 **4/12**。这些分母都很小，**只能视为指示性证据**。
2. **部分触发样本真实标签在候选组之外**，包括 `bull_mastiff`（2 张）、
   `kelpie`（1 张）、`rhodesian_ridgeback`（1 张）。候选提示表达的是
   "模型在这几个品种间难以区分"，**不代表候选中必有正确答案**。
3. **本实现不解决 APBT/AmStaff 的真实品种可分性问题**。V2.1 在该两类上的
   P/R/F1 仍低（见 `reports/v2_1_diagnostics/`），候选提示只是把模型的
   不确定性透明地呈现给用户。
4. **候选提示仍是低触发率功能**（四类 B1 约 0.58%），不是高频能力。
5. **`bull_mastiff` 被纳入组外误触发**：Bullmastiff 与四类外观高度相近，
   其被误判属可预期行为，但用户可能视为"误导性选项"——需人工判断可接受度。

---

## 5. 对 U5 既有报告统计口径的修订建议（**未改写原报告**）

> 按任务单要求，以下为**建议修订文本**，`reports/v2_1_candidate_ui_review/`
> 与 `reports/v2_1_apbt_four_breed_candidate_eval/` 中的原始证据文件
> **保持原样不动**。是否修订由人工决定。

### 5.1 三类基线"组内真实标签覆盖"应为 2/5，而非 3/5

`reports/v2_1_candidate_ui_review/acceptance_report.md` 记载三类策略
"触发样本中真标签确在组内 3/5（60%）"。U5.1 逐张复核确认：5 个触发样本
与清单完全一致，其中真标签在三类组内的实际是 **2 张**（AmStaff、SBT）；
第 3 张 `american_pit_bull_terrier` **不在**三类组内，属组外误触发。

**建议修订文本**：

> 触发样本中真实标签确在候选组内的为 **2/5（40%）**，另 3 张为组外误触发
> （`american_pit_bull_terrier`、`kelpie`、`rhodesian_ridgeback`）。

### 5.2 APBT 提示覆盖的正确口径：触发 4/13、未触发 9/13

U5.1 报告在描述 APBT 相关变化时，曾把"仍未触发的比例"表述为覆盖率。
**正确口径**为：validation split 中模型 Top-1 为 APBT 的样本共 **13 张**，
四类策略触发 **4/13（30.8%）**，**仍未触发 9/13（69.2%）**。

**建议修订文本**：

> 纳入 APBT 后，模型 Top-1 为 APBT 的 13 张验证样本中，四类策略触发
> **4 张（30.8%）**，仍未触发 **9 张（69.2%）**。相比三类策略的
> **0/13（0%）**，该盲区已显著缩小，但尚未完全覆盖。

### 5.3 U5.1 四类 B1 结果的口径提醒

U5.1 评估的四类 B1 结果为：触发 **12/2,079**、组内真实标签覆盖 **8/12**、
组外触发 **4/12**。上述分母均很小（触发样本仅 12 张），**只能视为指示性
证据**，不应作为强结论依据。

---

## 6. 输出文件

`reports/v2_1_four_breed_candidate_implementation/`：

| 文件 | 内容 |
|---|---|
| `implementation_report.md` | 本报告 |
| `acceptance_report.md` | 隔离环境 API/UI 实测验收结果 |
| `validation_samples_four_breed.csv` | 16 个代表性样本逐图明细（只用 val） |
| `acceptance_api_responses.json` | 隔离环境真实 API 响应留证（含全部 160 项检查明细） |
| `protection_snapshot_before.json` / `_after.json` | 保护快照（自动比对通过） |
| `git_status_before.txt` | 任务开始前 `git status --short` 原文 |

---

## 7. 保护核对

| 检查项 | 结果 |
|---|---|
| V1.1 `artifacts/best_model.pth` SHA256 | `89ef468f199c6d1550fec2638c5ea6f8ef7ad543e57f8ec82c4263c121b1a256` **一致** |
| V2.1 `best_model.pth` / `class_names.json` / `model_version.json` / `experiment_config.json` | SHA256 **一致** |
| `data/processed`、`processed_clean`、`raw`、`v2_processed`、`v2_processed_prev` 及 V1 备份 | 文件数与总字节 **一致** |
| SQLite | 142 条，`integrity_check: ok` |
| `uploads/` | 142 文件 |
| 后端 `weights_path` 默认值 | `artifacts/best_model.pth`，**未改** |
| `CATDOG_CANDIDATE_GROUP_ENABLED` 默认值 | `False`，**未改** |
| 训练 | **未调用任何训练脚本，未生成 V2.2 权重** |
| test split | **访问次数 0** |
| 图片标签 / 类别目录 | **未改**（未合并类别、未重命名、未增删图片） |
| 用户选择写库 | **未写**（DB 表字段与改动前完全一致） |

前后快照：`protection_snapshot_before.json` / `protection_snapshot_after.json`。

---

## 8. Git 状态（未提交、未清理）

本轮**未执行 `git commit`**，未自动 `git add`，未清理工作区，未覆盖任何
既有报告目录。开始前的 `git status --short` 原文见 `git_status_before.txt`。

**本任务修改/新增**：

```
 M backend/app/services/candidate_group.py     # 候选组三项→四项 + 版本升级
 M frontend/src/utils/breedNames.js            # APBT 中文名 + 四项候选组
 M tests/test_candidate_group.py               # 三项→四项 + 11 个新用例
 M frontend/tests/predictionResult.test.js     # radios 3→4 等
 M frontend/tests/predictionResultAcceptance.test.js  # 数据源切换
 M frontend/tests/breedNames.test.js          # CANDIDATE_GROUP 四项
?? scripts/accept_four_breed_candidate_api.py
?? reports/v2_1_four_breed_candidate_implementation/
?? md/U5.2_方案B1四类相近犬种候选组正式实现任务.md
```

**任务开始前已存在的未提交/未跟踪改动**（原样保留，未动）：
`M backend/app/{config,main}.py`、`backend/app/routes/predict.py`、
`backend/app/schemas.py`、`backend/app/services/predictor.py`、
`frontend/src/components/PredictionResult.vue`、`ml/predict.py`、
`ml/predictor.py`、`ml/train.py`、`tests/test_train_extensions.py`；
`?? artifacts/_v2_1_smoke/`、`artifacts/v2_1_136classes_seed42/`、
`backend/app/services/candidate_group.py`（本任务修改）、
`frontend/tests/predictionResult.test.js`（本任务修改）、
`md/` 下其他任务文档、`reports/` 下其他诊断目录、
`scripts/` 下其他诊断脚本、`tests/test_candidate_group.py`（本任务修改）。

---

**实施完成并停止，等待人工复核。未自动开启候选功能、未切换模型、未训练 V2.2。**
