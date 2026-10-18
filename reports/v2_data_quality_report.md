# V2 数据质量与防泄漏报告（U3）

> 生成时间：2026-10-18T09:20:53.114174+00:00
> 数据目录：`data/v2_processed/`（Git 忽略）
> 本阶段**不训练模型**。

## 1. 数据集组成

| 来源 | 类别数 | 说明 |
|---|---|---|
| Oxford-IIIT Pet（现有 37 类） | 37 | 原样复制 `data/processed_clean` 的 train/val/test，其 test 作为历史基准 |
| Stanford Dogs（新增品种） | 100 | 经质量/去重/防泄漏筛选后按 80/10/10 分层划分 |
| **合计** | **135** | 类别数由标准名称去重后的真实并集决定 |

## 2. 各 split 规模

| split | 类别数 | 图片数 |
|---|---|---|
| train | 135 | 16,525 |
| val | 135 | 2,062 |
| test | 135 | 5,346 |
| **合计** | **135** | **23,933** |

## 3. 质量检查

- 检查图片数：**16,686**
- 解码失败：**0**
- 分辨率过低（短边 < 64px）：**0**
- MD5 完全重复（同源内部）：**78**

## 4. 防泄漏检查（关键）

阈值：pHash（灰度 DCT 8×8）汉明距离 ≤ **5**

- 新增数据与 `data/processed_clean/test/` 的近重复对：**0**
- **因此被排除的外部图片：0 张**（原测试图片全部保留，未删除、未覆盖）
- 新增数据内部的近重复对：**56**
- 近重复簇数：16554（其中多图簇 52 个），**整簇原子分配到同一 split**

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
| `excluded_ambiguous_naming` | 2 |

完整清单见 `reports/v2_exclusion_manifest.csv`（共 80 条）。

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

## 7. 已知限制

1. **许可**：Stanford Dogs 为 ImageNet 衍生数据集，官方页面未声明独立
   许可证，仅限本地非商业教育研究用途；不得再分发。
2. **新增品种仅犬类**：本阶段未找到可审核通过的家猫品种数据源
   （CatInBeard 需授权、COCO 无品种标签、其余两个 HF 数据集不适用），
   因此猫类别仍为现有 12 种。
3. **3 个 Oxford 犬种未能与 Stanford 匹配**（`american_pit_bull_terrier`、
   `english_cocker_spaniel`、`scottish_terrier` 存在命名歧义），
   已保留 Oxford 数据、未与 Stanford 合并。
4. **重叠品种不合并**：19 个重叠犬种只使用 `data/processed_clean` 数据，
   Stanford 对应图片仅进入审计统计，不参与训练。
5. 新增品种的划分是本项目自建（80/10/10），与 Stanford 官方划分不同；
   本阶段**未用测试集做任何调参**。
