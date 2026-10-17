# 清洁（去重）数据划分报告

- 生成时间：2026-10-17T04:38:15.115921+00:00
- 输出目录：`E:\CatDogBreedNet\data\processed_clean`
- 参数：{'phash_threshold': 5, 'seed': 42, 'val_ratio': 0.1, 'phash_algorithm': '灰度 32x32 + 二维 DCT + 低频 8x8 中位数比特'}
- 算法：test = 官方 test.txt 原样全量复制（不排除、不改名、不改标签）；train/val = 官方 trainval.txt，先剔除与任一官方 test 图片 MD5 相同或 pHash 距离 <= threshold 的样本，再在剩余样本内按 pHash 阈值构建近重复簇（并查集 + 多索引分块检索），整簇按'原划分多数决、平局归 train'分配到 train/val；最后保证每个类别在 val 至少 1 个样本

## 样本数量对比

| 划分 | 原始 `data/processed` | 清洁 `data/processed_clean` | 差值 |
|---|---|---|---|
| train | 3311 | 3288 | -23 |
| val | 369 | 368 | -1 |
| test | 3669 | 3669 | +0 |

> test 数量不变；train/val 因排除泄漏样本而减少。两套划分的训练数据与选模过程已不同，指标不可作为同条件直接比较。

## 从 train/val 中排除的样本

- 合计排除 **24** 张
- 按原因：{'near_duplicate_with_test': 24}
- 按品种：{'Abyssinian': 1, 'Bombay': 1, 'British_Shorthair': 2, 'Egyptian_Mau': 2, 'german_shorthaired': 3, 'great_pyrenees': 1, 'japanese_chin': 6, 'keeshond': 4, 'leonberger': 2, 'newfoundland': 2}

## 近重复簇

- 近重复对：12
- 簇数：3645（含多张图片的簇 10 个）
- 因簇归属而调整的记录见 `clean_split_manifest.json` 的 `near_duplicate_clusters.reassigned_clusters`

## 校验结果

```json
{
  "class_sets_identical": true,
  "class_order_alphabetical": true,
  "md5_cross_split_duplicates": 0,
  "phash_cross_split_pairs": 0,
  "cluster_straddles": 0,
  "ok": true
}
```

## 复现方式

```powershell
cd E:\CatDogBreedNet
.venv\Scripts\python.exe scripts\build_clean_split.py
```

**本脚本只写 `data/processed_clean/`，未修改 `data/processed/`、官方原始档案或任何模型权重。**
