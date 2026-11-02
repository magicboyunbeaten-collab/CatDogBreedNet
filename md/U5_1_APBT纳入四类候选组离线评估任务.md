# U5.1：APBT 纳入四类相近犬种候选组——离线评估任务

## 任务目标

在现有 V2.1（136 类）候选模型基础上，评估将 APBT 纳入相近犬种候选策略的影响。目标候选组为四类：

1. `american_pit_bull_terrier` — 美国比特斗牛梗（APBT）
2. `american_staffordshire_terrier` — 美国斯塔福郡梗（AmStaff）
3. `staffordshire_bull_terrier` — 斯塔福郡斗牛梗（SBT）
4. `american_bulldog` — 美国斗牛犬（American Bulldog）

本阶段是**离线策略评估**，不是重新训练，也不是正式接入或切换模型。目的是验证四类候选组是否比当前三类候选组更能覆盖实际混淆场景，同时避免把明显不相关的犬种误导性地归入候选选项。

## 当前基线

- 正式模型仍为 V1.1：`artifacts/best_model.pth`（37 类）。不得修改或切换。
- V2.1 候选模型：`artifacts/v2_1_136classes_seed42/best_model.pth`。
- 类别映射：`artifacts/v2_1_136classes_seed42/class_names.json`。
- 当前三类候选组：AmStaff、SBT、American Bulldog。
- 当前规则：原始 Top-1 属于候选组，且候选组总概率质量 `group_mass >= 0.30`，组内第一、第二高概率差 `group_margin <= 0.40` 时触发。
- U5.1 之前已修复候选组只读取 Top-K 导致概率被截断的问题。评估必须使用**完整 136 类 softmax 概率向量**，不能把 Top-K 以外的候选当成 0 分。

## 严格范围

### 允许

- 读取当前 V2.1 checkpoint、对应 `class_names.json` 和 `experiment_config.json`。
- 对验证集 `data/v2_processed/val` 做推理及离线统计。
- 新增独立评估脚本与新报告目录。
- 只在验证集上扫描或比较候选规则阈值，并记录选择依据。
- 为对比结果生成 CSV、JSON、Markdown 报告。

### 禁止

- **禁止训练或微调任何模型**，不得调用训练脚本。
- 禁止读取 `data/v2_processed/test` 或用测试集挑选候选组、阈值、文案或策略。
- 禁止修改类别标签、图片、数据划分或任何原始数据目录。
- 本阶段先**不改动正式候选组实现**，只做离线模拟比较；禁止修改 `CANDIDATE_GROUP`、默认配置或正式 API/UI 行为。
- 不覆盖 `reports/v2_1_diagnostics/`、`reports/v2_1_coat_pitbull_diagnostics/`、`reports/v2_1_candidate_ui_review/` 中的现有文件。
- 不覆盖 V1.1 或 V2.1 checkpoint、`class_names.json`、`model_version.json`、`experiment_config.json`。
- 不修改 SQLite 数据库、`uploads/`、`data/processed_clean/`、`data/v2_processed/`、`data/v2_processed_prev/`。
- 不执行 `git reset --hard`、`git clean`、大范围 checkout/revert，不清理既有工作区改动，不执行 `git commit`。
- 不把图片、权重、数据库、上传记录加入 Git。

## 执行步骤

### 1. 记录运行前保护快照

在新报告目录保存 `protection_snapshot_before.json`，至少记录：

- V1.1 `artifacts/best_model.pth` 的 SHA256；
- V2.1 `best_model.pth`、`class_names.json`、`model_version.json`、`experiment_config.json` 的 SHA256（存在时）；
- `data/processed`、`data/processed_clean`、`data/raw`、`data/v2_processed`、`data/v2_processed_prev` 的文件数与总字节数；
- SQLite 行数、`PRAGMA integrity_check` 结果；
- `uploads/` 文件数；
- `git status --short` 原样输出。

不得为生成快照而加载/改写正式权重或数据。

### 2. 复现当前三类候选组基线

只读取验证集，使用当前完整 softmax 概率重新计算三类候选组策略，尽可能与现有报告对齐。验证：

- 验证集总样本数应为 2,079（如数据版本不同，以实际数量为准并解释）；
- Top-1 落入当前三类候选组的数量；
- 满足当前阈值的触发数量；
- 触发样本真实标签位于候选组内的数量/比例；
- 非候选真实标签被误导性地触发的数量/比例；
- 每张图片的完整预测和候选组概率明细。

若与既有 U5.1/U5 验收报告中的统计不同，先调查差异原因，不要直接更改阈值来凑数。

### 3. 离线模拟四类候选组

新增 APBT 后，候选组设为以上四类。至少实现并比较以下两种触发定义：

**定义 B1：沿用原逻辑**

- 原始 Top-1 属于四类候选组；
- `group_mass = 四类原始概率之和 >= 0.30`；
- `group_margin = 四类中最高概率 - 第二高概率 <= 0.40`。

**定义 B2：验证集阈值校准**

- 候选组仍固定为这四类，不得根据结果任意更改成员；
- 只使用 validation split 比较合理的 `group_mass` / `group_margin` 阈值组合；
- 明确记录阈值网格、触发数量、候选组真实标签覆盖率、误触发率及其权衡；
- 不能以提高触发数为唯一优化目标；也不能仅凭触发样本中“真标签在组内”的比例做判断而隐去漏检情况。
- 建议输出不同 `margin` 阈值（至少包括现有 0.40）与 `mass` 阈值的网格结果，供人工决策；如样本量不足以做稳健校准，应明确说明并优先保留保守规则。

如实现了 B2，最终建议阈值必须有可解释依据，不得读取 test split。

### 4. 重点错误分析

请单独统计并导出以下情况：

- 真实 APBT，被预测为 AmStaff / SBT / American Bulldog 的图片；
- 真实 AmStaff，被预测为 APBT / SBT / American Bulldog 的图片；
- 真实 SBT 和 American Bulldog 与另外三类间的误判；
- 模型 Top-1 属于四类，但真实标签为组外犬种（重点关注 Kelpie、Rhodesian Ridgeback 及其他组外类别）；
- Top-1 为 APBT、且四类组内仍存在明显竞争的样本；
- 当前三类策略不触发、但四类策略会触发的样本；
- 当前三类策略与四类策略都触发的样本。

每条记录至少包括：`split`（本任务只允许 val）、`image_path`、`true_label`、`top1_label`、`top1_probability`、四个候选类别的原始概率、`group_mass`、`group_margin`、三类策略是否触发、四类策略是否触发、触发原因。

### 5. 评价口径必须清楚

报告至少区分以下指标，不得混用：

- **触发率**：触发数 / 验证集总图片数；
- **组内真实标签覆盖率（触发样本精度口径）**：触发样本中真实标签属于四类之一的比例；
- **四类真实样本覆盖率（召回口径）**：真实标签属于这四类的样本中，有多少触发候选提示；
- **Top-1 命中率**：触发样本中模型 Top-1 正确的比例；
- **组外误触发率**：真实标签不在四类候选组的触发比例；
- **APBT 相关变化**：新增 APBT 后，真实 APBT 样本的候选提示覆盖率，以及模型 Top-1 为 APBT 的样本中有多少被提示。

所有比例同时给出分子、分母和百分比；分母很小时必须突出说明，不能据此下强结论。

### 6. 输出文件

在新目录 `reports/v2_1_apbt_four_breed_candidate_eval/` 中生成至少：

- `README.md`：本次评估范围、数据来源、禁止事项及运行方式；
- `evaluation_report.md`：中文总报告、结论和限制；
- `three_vs_four_group_summary.csv`：当前三类与扩展四类策略对比；
- `four_group_threshold_grid.csv`：B2 阈值网格结果；
- `four_group_validation_predictions.csv`：验证集逐图结果；
- `newly_triggered_by_apbt.csv`：因纳入 APBT 而新增触发的样本；
- `out_of_group_trigger_examples.csv`：触发但真实类别在候选组外的样本；
- `apbt_related_confusions.csv`：APBT 与另外三类相关的逐图混淆；
- `protection_snapshot_before.json`；
- `protection_snapshot_after.json`。

如果某份明细内容过大，可额外生成精简汇总，但不得省略完整的逐图 CSV。

### 7. 最终保护检查

完成后再次生成保护快照并比较。确认：

- V1.1 正式 checkpoint 哈希一致；
- V2.1 checkpoint、类别映射和配置哈希一致；
- 所有原始/处理数据目录文件数和总字节数一致；
- SQLite 行数与完整性一致，`uploads/` 文件数一致；
- 正式模型 `weights_path` 默认值和现有三类候选实现没有被修改；
- 未运行训练；未读取测试集；未改标签或图片；未提交 Git。

若任何保护检查失败，立即停止后续操作，在报告中如实说明，不要自行回滚或清理。

## 验收标准

- 当前三类基线和四类候选组均能用完整 softmax 概率重算。
- 对比统计全部基于 validation split，测试集访问记录为 0。
- 统计包括触发、覆盖、组外误触发和 APBT 新增覆盖，分子/分母清晰。
- 生成上述报告和 CSV，说明 B1 与 B2 差异并给出有证据的建议。
- 所有保护检查通过。
- 工作完成后停止，等待人工复核；不得自动修改正式候选组、开启功能、提交 Git 或开始 V2.2 训练。
