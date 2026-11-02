# APBT 纳入四类相近犬种候选组 —— 离线评估报告

> **阶段**：U5.1 离线策略评估（不训练、不切换模型、不改正式实现）
> **候选模型**：V2.1 `artifacts/v2_1_136classes_seed42/best_model.pth`（136 类）
> **正式模型**：V1.1 `artifacts/best_model.pth`（37 类），**未修改、未切换**
> **评估数据**：`data/v2_processed/val`（**仅 validation**，2,079 张）
> **报告目录**：`reports/v2_1_apbt_four_breed_candidate_eval/`（新建，未覆盖任何既有目录）
> **生成时间**：2026-10-19
> **测试集访问记录**：**0**（脚本只读 val，代码中不含 test 路径）

---

## 0. 总结论

1. **四类候选组显著扩大了对真实混淆场景的覆盖**：触发数 5 → 12（+140%），
   真实 APBT 样本的候选提示覆盖率 1/10（10%）→ 2/10（20%），
   Top-1 为 APBT 的样本中被提示的比例 0/13（0%）→ 4/13（30.8%）。
2. **代价是组外误触发同步上升**：组外误触发样本 3 → 4 张，触发样本的组内
   真实标签覆盖率 2/5（40%）→ 8/12（66.7%）——后者实际是**改善**的。
3. **Top-1 命中率反而下降**（2/5=40% → 5/12=41.7%，基本持平），说明新增
   触发主要覆盖的是"模型判错但组内确有竞争"的样本，符合候选提示的设计意图。
4. **B2 阈值网格没有找到帕累托改进**：最优组合（mass 0.40 / margin 0.60）
   虽把触发数提到 16、组内覆盖率提到 12/16（75%），但 margin 放宽到 0.60
   已超出"难以区分"的合理含义，且组外误触发仍有 4 张。
5. **建议：维持 B1（mass 0.30 / margin 0.40）作为四类候选组的触发规则**，
   即只把 APBT 加入候选组成员，不改阈值。理由见第 6 节。

> ⚠ **小分母警示**：四类真实样本仅 47 张，触发样本 5–17 张。以下所有比例
> **均为指示性参考**，不能据此下强结论，也不构成对正式策略的最终决策依据。

---

## 1. 数据与方法

| 项目 | 值 |
|---|---|
| 推理 | V2.1 best checkpoint，`build_transforms(train=False)`，batch 32，单次前向 |
| 概率口径 | **完整 136 维 softmax**，保留 10 位小数（不复用 Top-K 截断） |
| 策略判定 | 评估脚本内自含纯函数，**未 import 正式候选组实现** |
| 正式实现状态 | `CANDIDATE_GROUP` = (AmStaff, SBT, American Bulldog)，mass 0.30 / margin 0.40 —— **未修改** |
| 事实源 | `four_group_validation_predictions.csv`（2,079 行） |

策略定义：

- **三类基线**：Top-1 ∈ {AmStaff, SBT, AmBull} ∧ mass₃ ≥ 0.30 ∧ margin₃ ≤ 0.40
- **四类 B1**：Top-1 ∈ {APBT, AmStaff, SBT, AmBull} ∧ mass₄ ≥ 0.30 ∧ margin₄ ≤ 0.40
- **四类 B2**：同 B1 成员，阈值在 validation 上网格扫描

其中 `massₖ` = 候选组内原始概率之和；`marginₖ` = 组内最高 − 第二高原始概率。

---

## 2. 三类基线复现与差异调查（任务要求）

| 核对项 | 本次重算 | U5 验收报告 | 结论 |
|---|---|---|---|
| val 图片总数 | 2,079 | 2,079 | **一致** |
| Top-1 落入三类组 | 36 | 36 | **一致** |
| 三类策略触发数 | 5 | 5 | **一致** |
| 触发样本中真标签在组内 | **2** | **3** | **不一致，已调查** |

### 差异原因（已查明，非本次评估问题）

逐张比对显示：**5 个触发样本与 U5 清单完全一致**（5/5 交集，无增减）：

| 真实标签 | Top-1 | mass₃ | margin₃ | 真标签在三类组内 |
|---|---|---|---|---|
| `american_pit_bull_terrier` | AmStaff | 0.9963 | 0.0718 | **否** |
| `american_staffordshire_terrier` | AmStaff | 0.3794 | 0.3778 | 是 |
| `kelpie` | AmStaff | 0.3916 | 0.3885 | **否** |
| `rhodesian_ridgeback` | AmStaff | 0.8854 | 0.3461 | **否** |
| `staffordshire_bull_terrier` | SBT | 0.4572 | 0.3945 | 是 |

真标签在三类组内的实际是 **2 张**（AmStaff、SBT）。U5 报告写成 3/5，是把
真标签为 `american_pit_bull_terrier`（**不在**三类组内，属组外误触发）的
样本计入了"组内覆盖"。

**处理方式**：按任务要求"先调查差异原因，不直接改阈值凑数"——差异已定位为
U5 报告的统计口径错误，**本次未调整任何阈值**，并在此如实记录。
建议后续修订 `reports/v2_1_candidate_ui_review/acceptance_report.md` 中
该处数字（本轮不改动既有报告）。

---

## 3. 六口径对比（三类基线 vs 四类 B1）

| 口径 | 定义 | 三类基线 | 四类 B1 | 变化 |
|---|---|---|---|---|
| **触发率** | 触发数 / val 总图数 | 5 / 2,079（**0.2405%**） | 12 / 2,079（**0.5772%**） | 触发数 +140% |
| **组内真实标签覆盖率**<br>（触发样本精度口径） | 触发样本中真标签 ∈ 组的比例 | 2 / 5（**40.00%**）⚠小分母 | 8 / 12（**66.67%**）⚠小分母 | **+26.7 个百分点** |
| **四类真实样本覆盖率**<br>（召回口径） | 真标签 ∈ 组的样本中触发提示的比例 | 2 / 37（**5.4054%**）⚠小分母 | 8 / 47（**17.0213%**）⚠小分母 | 分子 ×4 |
| **Top-1 命中率** | 触发样本中 Top-1 正确的比例 | 2 / 5（**40.00%**）⚠小分母 | 5 / 12（**41.67%**）⚠小分母 | 基本持平 |
| **组外误触发率** | 真标签 ∉ 组的触发比例 | 3 / 5（**60.00%**）⚠小分母 | 4 / 12（**33.33%**）⚠小分母 | **−26.7 个百分点** |
| **APBT 相关变化** | 见下 | 1 / 10（**10.00%**）⚠小分母 | 2 / 10（**20.00%**）⚠小分母 | 分子 ×2 |

> 注：三类基线的"四类真实样本召回"分母为 37（三类组真实样本数），四类为 47
> （四类组真实样本数，含 APBT 10 张），**两个分母不同，不可直接横向比较**。
> 组内真实样本构成：APBT 10 / AmStaff 17 / SBT 10 / American Bulldog 10。

### APBT 相关变化明细

| 指标 | 三类基线 | 四类 B1 |
|---|---|---|
| 真实 APBT 样本的候选提示覆盖率 | 1 / 10（10.00%）⚠ | 2 / 10（20.00%）⚠ |
| Top-1 为 APBT 的样本中被提示的比例 | **0 / 13（0.00%）**⚠ | **4 / 13（30.77%）**⚠ |

**这是纳入 APBT 最直接的价值**：当前三类策略下，模型一旦把某张图判成 APBT，
候选提示**完全不出现**（0/13）——这正是 U5 验收报告记录的既定限制。四类策略
把这个盲区从 0% 降到 69.2%（13 张中 9 张仍不触发）。

---

## 4. 触发样本构成

### 4.1 三类基线触发（5 张）

| 真实标签 | Top-1 | p(Top-1) | 组内判定 |
|---|---|---|---|
| `american_pit_bull_terrier` | AmStaff | 0.5337 | 组外误触发 |
| `american_staffordshire_terrier` | AmStaff | 0.3786 | 组内 ✓ |
| `kelpie` | AmStaff | 0.3900 | 组外误触发 |
| `rhodesian_ridgeback` | AmStaff | 0.5991 | 组外误触发 |
| `staffordshire_bull_terrier` | SBT | 0.4256 | 组内 ✓ |

### 4.2 四类 B1 触发（12 张）

= 上述 5 张（`triggered_by_both_strategies.csv`）+ 新增 7 张。

### 4.3 因纳入 APBT 新增触发（7 张，`newly_triggered_by_apbt.csv`）

| 真实标签 | Top-1 | p(Top-1) | p(APBT) | mass₄ | margin₄ |
|---|---|---|---|---|---|
| `american_pit_bull_terrier` | **APBT** | 0.4672 | 0.4672 | 0.8581 | 0.0763 |
| `american_staffordshire_terrier` | **APBT** | 0.6081 | 0.6081 | 0.9931 | 0.3531 |
| `american_staffordshire_terrier` | **APBT** | 0.6195 | 0.6195 | 0.9995 | 0.2394 |
| `american_staffordshire_terrier` | AmStaff | 0.4656 | 0.1016 | 0.5686 | 0.3640 |
| `american_staffordshire_terrier` | AmStaff | 0.5290 | 0.4651 | 0.9943 | 0.0639 |
| `bull_mastiff` | **APBT** | 0.4709 | 0.4709 | 0.7547 | 0.1903 |
| `bull_mastiff` | AmStaff | 0.4569 | 0.0970 | 0.5548 | 0.3599 |

**观察**：7 张新增中 3 张 Top-1 就是 APBT（其中 1 张真实 APBT 判对、2 张真实
AmStaff 被误判为 APBT、另加 2 张 bull_mastiff）。这说明纳入 APBT 后，
"模型判成 APBT"的场景开始有提示，与设计意图一致；但 **bull_mastiff 有 2 张
被误纳入**——Bullmastiff 本就是 APBT/AmStaff 的邻近品种，其被误判属组外误触发。

### 4.4 组外误触发（4 张，`out_of_group_trigger_examples.csv`）

| 触发策略 | 真实标签 | Top-1 | p(Top-1) |
|---|---|---|---|
| 三类 | `kelpie` | AmStaff | 0.3900 |
| 三类 | `rhodesian_ridgeback` | AmStaff | 0.5991 |
| 四类 | `bull_mastiff` | APBT | 0.4709 |
| 四类 | `bull_mastiff` | AmStaff | 0.4569 |

任务单特别点名 Kelpie 与 Rhodesian Ridgeback——这两张在三类策略下就已误触发，
**纳入 APBT 并未新增这两类误触发**；新增的 2 张组外误触发全部来自
`bull_mastiff`（本身与四类外观高度相近的品种）。

---

## 5. B2 阈值网格（63 组合，仅 validation）

完整结果见 `four_group_threshold_grid.csv`（mass 7 档 × margin 9 档）。

### 5.1 关键切片

**固定 mass = 0.30（现有），扫描 margin：**

| margin | 触发 | 组内覆盖 | 四类召回 | Top-1 命中 | 组外误触发 |
|---|---|---|---|---|---|
| 0.05 | 0 | 0/0 | 0/47 | 0/0 | 0 |
| 0.10 | 3 | 3/3 (100%) | 3/47 (6.38%) | 3/3 (100%) | 0 |
| 0.15 | 3 | 3/3 (100%) | 3/47 (6.38%) | 3/3 (100%) | 0 |
| 0.20 | 4 | 3/4 (75%) | 3/47 (6.38%) | 3/4 (75%) | 1 |
| 0.25 | 5 | 4/5 (80%) | 4/47 (8.51%) | 4/5 (80%) | 1 |
| 0.30 | 6 | 5/6 (83.3%) | 5/47 (10.6%) | 5/6 (83.3%) | 1 |
| **0.40（B1）** | **12** | **8/12 (66.7%)** | **8/47 (17.0%)** | **5/12 (41.7%)** | **4** |
| 0.50 | 13 | 8/13 (61.5%) | 8/47 (17.0%) | 5/13 (38.5%) | 5 |
| 0.60 | 17 | 12/17 (70.6%) | 12/47 (25.5%) | 8/17 (47.1%) | 5 |

**固定 margin = 0.40（现有），扫描 mass：**

| mass | 触发 | 组内覆盖 | 四类召回 | 组外误触发 |
|---|---|---|---|---|
| 0.10 – 0.30 | 12 | 8/12 (66.7%) | 8/47 (17.0%) | 4 |
| 0.40 | 11 | 8/11 (72.7%) | 8/47 (17.0%) | 3 |
| 0.50 | 10 | 7/10 (70.0%) | 7/47 (14.9%) | 3 |

### 5.2 网格结论

1. **mass 阈值在 0.10–0.30 之间完全不敏感**（触发数恒为 12）：能触发的样本
   组内总质量都很高（≥0.55），mass 门槛在此区间不起过滤作用。把 mass 提到
   0.40 只减少 1 个触发、减少 1 个组外误触发。
2. **margin 是真正的主控参数**：0.05→0.60 触发数 0→17。但 margin ≥ 0.50 时
   组内最高与第二高的原始概率差已超过 0.5，**不再符合"模型难以区分"的语义**。
3. **没有帕累托改进组合**：任何提高召回/触发数的组合都伴随组外误触发上升或
   margin 语义失效。B1（0.30 / 0.40）位于合理语义边界上。

---

## 6. 结论与建议

### 6.1 有数据支持的观察

| # | 观察 | 证据 |
|---|---|---|
| 1 | 四类候选组把触发数从 5 提到 12，组内真实标签覆盖率从 40% 提到 66.7%，组外误触发率从 60% 降到 33.3% | `evaluation_summary.json` 第 3 节口径表 |
| 2 | 纳入 APBT 消除了"Top-1 为 APBT 时候选提示完全不出现"的盲区（0/13 → 4/13） | 同上 `apbt_top1_trigger_rate` |
| 3 | 新增的 7 个触发中 3 个 Top-1 就是 APBT，2 个来自 bull_mastiff | `newly_triggered_by_apbt.csv` |
| 4 | 三类基线触发的 5 张中有 3 张是组外误触发（含任务点名的 kelpie 与 rhodesian_ridgeback），该问题**不是**纳入 APBT 造成的 | `out_of_group_trigger_examples.csv` |
| 5 | mass 阈值在 0.10–0.30 区间对触发结果无影响；margin 是主控参数 | `four_group_threshold_grid.csv` 第 5.1 节 |
| 6 | U5 报告的"组内 3/5"是统计口径错误，实际为 2/5；5 个触发样本本身与 U5 清单一致 | 第 2 节逐张比对 |

### 6.2 建议

**建议维持 B1（mass 0.30 / margin 0.40）作为四类候选组的触发规则，即只把
APBT 加入候选组成员，不改阈值。**

依据：

1. B1 在**组内覆盖率（66.7%）与组外误触发率（33.3%）两个方向同时优于**三类
   基线（40% / 60%），是唯一一个双向改善的组合；
2. B2 网格中唯一召回更高的组合（mass 0.40 / margin 0.60）需要把 margin 放宽
   到 0.60，此时"组内最高与第二高概率差 ≤ 0.60"已不能表达"模型难以区分"，
   且组外误触发仍有 4 张，**不构成帕累托改进**；
3. 任务单明确"不能以提高触发数为唯一优化目标"，而 17 个触发里 Top-1 正确
   仅 8 个（47.1%），放宽阈值会引入更多低质量提示；
4. 四类真实样本仅 47 张、触发样本 ≤17 张，**样本量不足以支撑激进校准**，
   按任务要求"优先保留保守规则"。

**这是离线评估结论，不构成对正式策略的最终决策。** 是否真正把 APBT 纳入
正式候选组，需人工评审后另行修改 `backend/app/services/candidate_group.py`。

### 6.3 尚未验证的假设

1. **组外误触发的可接受度**：`bull_mastiff` 被误纳入是否会被用户视为"误导性
   选项"，需人工判断 Bullmastiff 与四类的邻近程度是否可接受。
2. **触发率是否过低**：四类 B1 触发率仍只有 0.58%，若产品需要更高频提示，
   需重新评估整个候选提示的价值定位（本轮未做用户研究）。
3. **val 与 test 上的稳定性**：本轮只用 val，未在 test 上验证（任务禁止）。
   47 张真实样本的统计在另一个 split 上可能明显波动。
4. **APBT 判对样本的提示必要性**：新增触发中有 1 张是真实 APBT 且模型判对
   （p=0.4672，组内 margin 仅 0.0763）——此时提示是否有实际帮助，需人工判断。

---

## 7. 重点错误分析汇总

| 类别 | 数量 | 输出 |
|---|---|---|
| 真实 APBT → 另外三类 | 1 | `apbt_related_confusions.csv` |
| 真实 AmStaff → APBT/SBT/AmBull | 4 | 同上 |
| 真实 SBT/AmBull → 另外三类 | 1 | 同上 |
| Top-1 ∈ 四类但真标签组外 | 4（kelpie 1、rhodesian_ridgeback 1、bull_mastiff 2） | `out_of_group_trigger_examples.csv` |
| Top-1 为 APBT 且组内 margin ≤ 0.40 | 4 | `apbt_related_confusions.csv` |
| 三类不触发、四类触发 | 7 | `newly_triggered_by_apbt.csv` |
| 三类与四类都触发 | 5 | `triggered_by_both_strategies.csv` |

每条记录均含 `split / image_path / true_label / top1_label /
top1_probability / p_apbt / p_amstaff / p_sbt / p_ambull / group_mass_3 /
group_margin_3 / triggered_3 / reason_3 / group_mass_4 / group_margin_4 /
triggered_4 / reason_4`，满足任务单字段要求。

---

## 8. 保护核对

| 检查项 | 结果 |
|---|---|
| V1.1 `artifacts/best_model.pth` SHA256 | `89ef468f…a256` **一致**（与任务单期望值相同） |
| V2.1 `best_model.pth` / `class_names.json` / `model_version.json` / `experiment_config.json` | SHA256 **一致** |
| `data/processed`、`processed_clean`、`raw`、`v2_processed`、`v2_processed_prev` | 文件数与总字节 **一致** |
| SQLite | 142 条，`integrity_check: ok` |
| `uploads/` | 142 文件 |
| 正式模型 `weights_path` 默认值 | `artifacts/best_model.pth`，**未改** |
| 正式三类候选实现 | `CANDIDATE_GROUP` = (AmStaff, SBT, American Bulldog)，mass 0.30 / margin 0.40，**未改** |
| 训练 | **未运行任何训练脚本** |
| test split | **访问次数 0** |

前后快照：`protection_snapshot_before.json` / `protection_snapshot_after.json`
（由 `scripts/diagnostic_protection_snapshot.py --phase before/after --out-dir`
生成并自动比对）。

---

## 9. 输出文件

`reports/v2_1_apbt_four_breed_candidate_eval/`：`README.md`、
`evaluation_report.md`、`three_vs_four_group_summary.csv`、
`four_group_threshold_grid.csv`、`four_group_validation_predictions.csv`、
`four_group_validation_predictions_slim.csv`、`newly_triggered_by_apbt.csv`、
`triggered_by_both_strategies.csv`、`out_of_group_trigger_examples.csv`、
`apbt_related_confusions.csv`、`evaluation_summary.json`、
`protection_snapshot_before.json`、`protection_snapshot_after.json`。

---

## 10. Git 状态

本轮**未执行 `git commit`**，未清理工作区，未覆盖既有诊断报告。新增：

```
?? scripts/evaluate_apbt_four_group.py
?? reports/v2_1_apbt_four_breed_candidate_eval/
?? md/U5_1_APBT纳入四类候选组离线评估任务.md
```

其余 `M` / `??` 项均为本任务开始前既有改动，原样保留。

---

**评估完成并停止，等待人工复核。未自动修改正式候选组、未开启功能、未提交
Git、未开始 V2.2 训练。**
