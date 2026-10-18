# V2 数据质量与防泄漏报告（U3）

> 生成时间：2026-10-18T11:08:58.901896+00:00
> 数据目录：`data/v2_processed/`（Git 忽略）
> 本阶段**不训练模型**。

## 1. 数据集组成

> **两个数字必须区分**：`catalog_rows` 是类别目录的**候选行数**，`valid_class_count` 是剔除被排除候选后的**最终有效类别数**。下表「最终有效类别数」取自实际 `manifest.json` 与数据目录。

| 项目 | 数量 | 说明 |
|---|---|---|
| 类别目录候选行数 | **137** | Oxford 37 + Stanford 候选 100 |
| 被排除的候选类别 | **1** | `cocker_spaniel` |
| **最终有效类别数** | **136** | 现有 37 + 新增 99；由标准名称去重后的真实并集决定 |

各来源明细：

| 来源 | 有效类别数 | 说明 |
|---|---|---|
| Oxford-IIIT Pet（现有 37 类） | 37 | 原样复制 `data/processed_clean` 的 train/val/test，其 test 作为历史基准 |
| Stanford Dogs（新增有效品种） | 99 | 经质量/去重/防泄漏筛选后按 80/10/10 分层划分 |
| **合计** | **136** | |

被排除的候选类别及理由：

- `cocker_spaniel`（`n02102318-cocker_spaniel`，原始 159 张）：来源标签无法可靠区分美式/英式可卡犬（ImageNet 仅标注为 cocker_spaniel）；不进行猜测性重标，故本阶段不纳入 V2。Oxford 的 english_cocker_spaniel 类别完整保留，不与本类合并。

## 2. 各 split 规模

| split | 类别数 | 图片数 |
|---|---|---|
| train | 136 | 16,655 |
| val | 136 | 2,079 |
| test | 136 | 5,363 |
| **合计** | **136** | **24,097** |

## 3. 质量检查

- 检查图片数：**16,850**
- 解码失败：**0**
- 分辨率过低（短边 < 64px）：**0**
- MD5 完全重复（同源内部）：**78**

## 4. 防泄漏检查（关键）

阈值：pHash（灰度 DCT 8×8）汉明距离 ≤ **5**

- 新增数据与 `data/processed_clean/test/` 的近重复对：**0**
- **因此被排除的外部图片：0 张**（原测试图片全部保留，未删除、未覆盖）
- 新增数据内部的近重复对：**56**
- 近重复簇数：16718（其中多图簇 52 个），**整簇原子分配到同一 split**

### 4.1 V2 划分内部跨集合检查

| 检查项 | 结果 |
|---|---|
| 各 split 类别集合一致 | **True** |
| MD5 跨 split 完全重复 | **0** |
| pHash 跨 split 近重复对（≤5） | **0** |

## 5. 排除清单摘要

| 原因 | 数量 |
|---|---|
| `md5_exact_duplicate` | 78 |
| `excluded_ambiguous_naming` | 1 |

完整清单见 `reports/v2_exclusion_manifest.csv`（共 79 条）。

## 6. 可复现性

- 随机种子：**42**
- 划分脚本：`scripts/build_v2_dataset.py`
- 标签目录：`reports/v2_class_catalog.json`
- 校验脚本：`scripts/verify_v2_dataset.py`

```powershell
cd E:\CatDogBreedNet
.venv\Scripts\python.exe scripts\fetch_stanford_dogs.py
.venv\Scripts\python.exe scripts\build_v2_class_catalog.py
.venv\Scripts\python.exe scripts\build_v2_dataset.py
.venv\Scripts\python.exe scripts\verify_v2_dataset.py
```

## 7. 已知限制与口径说明

1. **许可**：Stanford Dogs 为 ImageNet 衍生数据集，官方页面未声明独立
   许可证，仅限本地非商业教育研究用途；**不得再分发**原始或处理后的图片。
   论文需按审核报告要求引用 Khosla et al. (FGVC@CVPR 2011) 与 Deng et al. (CVPR 2009)。
2. **新增品种仅犬类**：本阶段未找到可审核通过的家猫品种数据源
   （CatInBeard 需授权、COCO 无品种标签、其余两个 HF 数据集不适用），
   因此猫类别仍为现有 12 种。
3. **Oxford 犬种与 Stanford 的对应关系分为三类**（不可混为一谈）：
   - **已确切对应 20 个**：经归一化或人工核验别名与 Stanford 一一对应，其中包含 `scottish_terrier` ↔ `Scotch_terrier`（Scotch 是 Scottish 的旧同义名，属**已验证别名**，不再按命名歧义处理）。按既定决策**只使用 Oxford 数据**，Stanford 图片仅入审计统计、不合并训练。
   - **有相似类别但按口径不合并 2 个**：
     - `american_pit_bull_terrier`：American Pit Bull Terrier（APBT）保留原有类别与原始数据不变；Stanford 的 American_Staffordshire_terrier（AmStaff）按**独立新增类别**纳入 V2（canonical: american_staffordshire_terrier），不作为 APBT 的别名，两类图片不合并
     - `english_cocker_spaniel`：english_cocker_spaniel 类别完整保留，不改名、不删除；Stanford 的 cocker_spaniel 因来源标签无法可靠区分美式/英式可卡犬而保持排除，不与本类合并
   - **确实没有对应类别 15 个**：其中猫 12 个（Stanford Dogs 仅含犬种，属预期），犬 3 个（`american_bulldog`、`havanese`、`shiba_inu`）。
4. **`cocker_spaniel` 保持排除**：Stanford 的来源标签无法可靠区分
   美式/英式可卡犬，**不做猜测性重标**；Oxford 的 `english_cocker_spaniel` 完整保留，两者不合并。
5. **重叠品种不合并**：20 个重叠犬种只使用 `data/processed_clean` 数据，Stanford 对应图片仅进入审计统计，不参与训练。
6. 新增品种的划分是本项目自建（80/10/10），与 Stanford 官方划分不同；
   本阶段**未用测试集做任何调参**。
