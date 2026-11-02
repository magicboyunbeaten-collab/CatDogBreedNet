# U5.2 验收报告口径核对与勘误说明

> **性质**：新建的补充说明文档。**不覆盖、不改写**任何既有报告。
> **被核对对象**：`reports/v2_1_four_breed_candidate_implementation/acceptance_report.md`
> 及其引用的 `validation_samples_four_breed.csv`、`acceptance_api_responses.json`，
> 以及 `reports/v2_1_apbt_four_breed_candidate_eval/` 下三份代表性清单。
> **复算脚本**：`scripts/reconcile_u5_2_numbers.py`（只读）
> **复算结果**：`reconcile_stats.json`
> **生成时间**：2026-10-19

---

## 0. 结论速览

**U5.2 的 160/160 通过结论成立，未发现实质性的判定错误。**
但有 **3 处表述口径**会让读者误读数字（把"记录数"读成"图片数"），
建议在后续文档中按第 4 节修订。**本文件不改动任何原始证据文件。**

---

## 1. 四个基础数字（复算实测）

| 数字 | 项目 | 实测值 | 定义 |
|---|---|---|---|
| **19** | 来源**记录**数 | **19** | 三份 U5.1 清单 16 条 + 未触发对照 3 条 |
| **16** | 代表样本 CSV **行**数 | **16** | 7（newly）+ 5（both）+ 4（out_of_group） |
| **12** | 四类**实际触发**的**唯一图片**数 | **12** | 7（newly）+ 5（both）；两者互斥 |
| **3** | 未触发对照图片数 | **3** | val 中非候选类（Abyssinian ×3） |
| **160** | API 验收**检查项**数 | **160** | 每张图 6–8 项断言累加，**不是样本数** |

**唯一图片数**（去重后）：三份清单 **12 张** + 对照 **3 张** = **15 张**。
因此"19"与"15"是**同一批数据的两种口径**，不可混用。

---

## 2. 四条数字之间的关系链

```
U5.1 三份清单（记录）
├── newly_triggered_by_apbt.csv        7 条 ─┐
├── triggered_by_both_strategies.csv   5 条 ─┤→ 互斥，合计 12 张唯一触发图
└── out_of_group_trigger_examples.csv  4 条 ─┘   └─ 这 4 条全部已包含在上面 12 张内
                                              （是"重列"，不是额外样本）
        ↓
   记录合计 16 条  →  validation_samples_four_breed.csv 写 16 行（含 4 行重复）
        ↓
   + 未触发对照 3 条
        ↓
   来源记录 19 条  →  唯一图片 15 张（12 触发 + 3 对照）
        ↓
   逐图走 POST /api/predict，累计 160 项检查
```

### 2.1 关键事实：`out_of_group` 是 `newly`/`both` 的子集

复算结果：

| 交叉项 | 实测 | 说明 |
|---|---|---|
| `newly` ∩ `both` | **0 张** | 二者定义互斥（三类不触发 vs 三类也触发），符合预期 |
| `out_of_group` 独有的新图片 | **0 张** | 它是那 12 张的子集 |

那 4 张重复记录的图片是：

| 图片 | 同时出现在 |
|---|---|
| `bull_mastiff/n02108422_3297.jpg` | `newly_triggered_by_apbt` + `out_of_group` |
| `bull_mastiff/n02108422_5619.jpg` | `newly_triggered_by_apbt` + `out_of_group` |
| `kelpie/n02105412_133.jpg` | `triggered_by_both` + `out_of_group` |
| `rhodesian_ridgeback/n02087394_9698.jpg` | `triggered_by_both` + `out_of_group` |

**逻辑上完全合理**：这 4 张既"因纳入 APBT 而新增触发"，又"真实标签在四类之外"，
所以同时属于两个分类视角。它们不是新样本。

---

## 3. 发现的三处口径问题（均不影响通过结论）

### 3.1 "合计 19" 未区分记录数与唯一图片数

**原文位置**：`acceptance_report.md` 第 2 节样本来源表末行
「**合计** | **19** | 全部位于 `data/v2_processed/val`」。

**问题**：读者容易把 19 理解为"19 张唯一图片"，实际是 **19 条记录**，
对应 **15 张唯一图片**（12 触发 + 3 对照）。

**影响**：仅表述；不影响 160/160 判定。

### 3.2 `validation_samples_four_breed.csv` 存在 4 行重复

**原文位置**：`acceptance_report.md` 第 2 节「逐图明细：`validation_samples_four_breed.csv`（16 行代表性样本）」。

**实测**：CSV 共 16 行，但 `sample_id` 唯一值只有 **12** 个——
`out_of_group` 的 4 张与 `newly`/`both` 重叠，同一张图被写了两行
（`source` 字段不同）。

**影响**：若有人按行数当作"验证了 16 张不同图片"会高估覆盖面。
实际覆盖 12 张唯一触发图。

### 3.3 `evidence.triggered` 重复上传了 4 张

**原文位置**：`acceptance_report.md` 第 3 节「A1 代表性样本 `triggered == true` | PASS（16/16）」。

**实测**：`acceptance_api_responses.json` 的 `evidence.triggered` 有 **16 条记录**，
但只对应 **12 张唯一图片**——脚本对同一批图按三份清单各跑了一遍，
那 4 张重叠图被重复 `POST /api/predict` 了两次。

**影响**：断言全部通过且重复验证无害；但"16/16"应理解为"16 次请求"，
不是"16 张不同图片"。

---

## 4. 建议修订文本（供人工决定，**本轮未修改原文件**）

### 4.1 对 `acceptance_report.md` 第 2 节表格的修订建议

把末行改为：

> | 未触发对照（val 中非候选类） | 3 |
> | **记录合计** | **19 条**（对应**唯一图片 15 张**：12 张触发 + 3 张对照） |
>
> 注：`newly_triggered_by_apbt`（7）与 `triggered_by_both_strategies`（5）
> 互斥，合计 **12 张唯一触发图**；`out_of_group_trigger_examples`（4）是这
> 12 张的子集，属分类视角的重列，不构成额外样本。

### 4.2 对 `validation_samples_four_breed.csv` 的说明补充

建议在该节增加一句：

> 该 CSV 共 16 行，但 `sample_id` 唯一值仅 **12** 个；
> `out_of_group` 的 4 张与 `newly`/`both` 重叠，同图以不同 `source` 各记一行。
> 按"验证覆盖"口径应读作 **12 张唯一触发图**。

### 4.3 对第 3 节 A1 的修订建议

把「PASS（16/16）」改为：

> PASS（16 次请求全部通过，覆盖 **12 张唯一触发图**）

---

## 5. 未发现问题的部分（明确确认）

以下 U5.2 报告内容经复算**与数据一致**，无需修订：

| 项目 | 复核结果 |
|---|---|
| API 验收检查项总数 160、全部通过 | **一致** |
| 关闭开关复测 12 次 | **一致**（`evidence.switch_off` = 12） |
| 未触发对照 3 张 | **一致** |
| 候选组成员为四项（含 APBT） | **一致** |
| `threshold_version = val-2026-10-19-four-breed-b1` | **一致** |
| 「与 U5.1 清单逐张一致」的 12 张 | **一致**（唯一图片恰为 12） |
| U5 三类基线"组内 2/5"的勘误说明 | 已在 U5.2 `implementation_report.md` 第 5 节给出，本轮复核一致 |

---

## 6. 复现方式

```powershell
cd E:\CatDogBreedNet
.venv\Scripts\python.exe scripts/reconcile_u5_2_numbers.py
```

输出 `reports/v2_1_four_breed_page_acceptance/reconcile_stats.json`，
其中 `relations.out_of_group_is_subset_of_12 = true` 即为本文件 2.1 节的机器证明。

---

## 7. 声明

- 本文件为**新建**文档，**未修改** `reports/v2_1_four_breed_candidate_implementation/`
  与 `reports/v2_1_apbt_four_breed_candidate_eval/` 中的任何文件。
- 第 4 节的修订文本仅为**建议**，需人工确认后再决定是否应用。
- 未因此次核对而调整任何阈值、候选组成员或验收判据。
