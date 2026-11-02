# U5.1：APBT 纳入四类相近犬种候选组 —— 离线评估

## 评估范围

在现有 V2.1（136 类）**候选模型**基础上，评估将 APBT 纳入相近犬种候选策略的影响。

- **候选模型**：`artifacts/v2_1_136classes_seed42/best_model.pth`（136 类）
- **类别映射**：`artifacts/v2_1_136classes_seed42/class_names.json`
- **评估数据**：`data/v2_processed/val`（**仅 validation split**，2,079 张）
- **候选组（四类，成员固定）**：
  - `american_pit_bull_terrier` — 美国比特斗牛梗（APBT）
  - `american_staffordshire_terrier` — 美国斯塔福郡梗（AmStaff）
  - `staffordshire_bull_terrier` — 斯塔福郡斗牛梗（SBT）
  - `american_bulldog` — 美国斗牛犬（American Bulldog）
- **对照基线（三类，当前正式）**：AmStaff / SBT / American Bulldog
- **当前正式规则**：Top-1 ∈ 候选组 ∧ `group_mass ≥ 0.30` ∧ `group_margin ≤ 0.40`

## 数据来源与口径

- 全部统计基于**完整 136 维 softmax 概率向量**（保留 10 位小数）。
  U5.1 之前已修复候选组只读取 Top-K 导致概率被截断的问题，本评估**不复用
  Top-K 截断概率**，Top-K 以外的候选不会被视为 0 分。
- 单一事实源：`four_group_validation_predictions.csv`（2,079 行逐图明细，
  含 `probabilities_json`）。所有策略、网格、错误分析均从该文件派生，
  各口径分子分母可相互核对。
- **测试集访问记录为 0**：脚本只 `rglob` val 目录，代码中不出现任何 test 路径。

## 禁止事项（本轮严格执行）

- 禁止训练或微调任何模型，未调用任何训练脚本。
- **禁止读取 `data/v2_processed/test`**，未用测试集挑选候选组、阈值或策略。
- 禁止修改类别标签、图片、数据划分或任何原始数据目录。
- **未改动正式候选组实现**：`backend/app/services/candidate_group.py` 的
  `CANDIDATE_GROUP`、`MASS_THRESHOLD`、`MARGIN_THRESHOLD` 与默认配置均未修改，
  正式三类行为保持不变；本评估的策略函数全部自含在评估脚本内。
- 未覆盖 `reports/v2_1_diagnostics/`、`reports/v2_1_coat_pitbull_diagnostics/`、
  `reports/v2_1_candidate_ui_review/` 中的任何现有文件。
- 未覆盖 V1.1 / V2.1 checkpoint、`class_names.json`、`model_version.json`、
  `experiment_config.json`。
- 未修改 SQLite、`uploads/`、`data/processed_clean/`、`data/v2_processed/`、
  `data/v2_processed_prev/`。
- 未执行 `git reset --hard` / `git clean` / 大范围 checkout/revert，
  未清理既有工作区改动，**未执行 `git commit`**。
- 未把图片、权重、数据库、上传记录加入 Git。

## 运行方式

```powershell
cd E:\CatDogBreedNet
# 完整运行（val 一次前向，约 1-2 分钟）
.venv\Scripts\python.exe scripts/evaluate_apbt_four_group.py
# 复用已有逐图 CSV 重算策略（跳过推理）
.venv\Scripts\python.exe scripts/evaluate_apbt_four_group.py --reuse
```

可选参数：`--model-dir`、`--val-dir`、`--out-dir`、`--device`、`--reuse`。

## 输出文件

| 文件 | 内容 |
|---|---|
| `evaluation_report.md` | 中文总报告、结论与限制 |
| `three_vs_four_group_summary.csv` | 三类基线 / 四类 B1 六口径对比 |
| `four_group_threshold_grid.csv` | B2 阈值网格（mass 7 档 × margin 9 档 = 63 组合） |
| `four_group_validation_predictions.csv` | 逐图完整明细（含 136 维概率 JSON 与三类/四类判定） |
| `four_group_validation_predictions_slim.csv` | 精简版（不含 136 维概率，便于人工浏览） |
| `newly_triggered_by_apbt.csv` | 三类不触发但四类触发的样本 |
| `triggered_by_both_strategies.csv` | 三类与四类都触发的样本 |
| `out_of_group_trigger_examples.csv` | 触发但真实类别在四类之外的样本 |
| `apbt_related_confusions.csv` | APBT 与另外三类的逐图混淆 |
| `evaluation_summary.json` | 机器可读汇总（含与 U5 报告的基线核对） |
| `protection_snapshot_before.json` / `_after.json` | 保护快照（自动比对） |

## 重要说明：小分母

validation split 中四类候选的真实样本仅 **47 张**（APBT 10 / AmStaff 17 /
SBT 10 / American Bulldog 10），触发样本数在 5–17 张之间。**所有涉及这些
分母的比例都必须视为指示性参考**，报告中已用"小分母"标记，不能据此下强结论。

## 与 U5 验收报告的一处差异（已调查）

U5 验收报告记载三类策略"触发样本中真标签在组内 3/5"，本次重算为 **2/5**。
经逐张核对，5 个触发样本与 U5 清单**完全一致**，差异源于 U5 报告把一张
真标签为 `american_pit_bull_terrier`（不在三类组内）的样本计入了"组内覆盖"。
详见 `evaluation_report.md` 第 2 节。**未据此调整任何阈值。**
