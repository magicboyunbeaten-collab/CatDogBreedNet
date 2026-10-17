# 模型诊断报告（U1）

- 生成时间：2026-10-17T02:44:55.855639+00:00
- 诊断对象：阶段 2 训练的 ResNet18 基线（`artifacts/best_model.pth`，37 类）
- 数据目录：`E:\CatDogBreedNet\data\processed`（只读扫描，未修改任何文件）
- 随机种子：42；train/val 划分比例：0.1
- 本报告**不重训、不覆盖任何基线权重与既有报告**；
  所有数字来自本次真实运行，未验证的假设均明确标注。

## 1. 数据规模与分布（重新扫描磁盘）

| 子集 | 总数 | 每类最少 | 每类最多 | 每类均值 | 每类中位数 |
|---|---|---|---|---|---|
| train | 3311 | 84 | 90 | 89.49 | 90 |
| val | 369 | 9 | 10 | 9.97 | 10 |
| test | 3669 | 88 | 100 | 99.16 | 100 |

- 类别数：**37**（三个子集一致）
- train 每类样本区间 84–90，极差仅 6 张。
- 样本量最少的 5 类：Egyptian_Mau(84)、Bombay(86)、english_cocker_spaniel(86)、newfoundland(86)、Siamese(89)

## 2. 标签映射一致性

| 检查项 | 结果 |
|---|---|
| 三个子集类别集合一致 | 是 |
| 三个子集类名顺序一致 | 是 |
| train 顺序为字典序（ImageFolder 约定） | 是 |

各类别数量：{'train': 37, 'val': 37, 'test': 37}

与 `artifacts/class_names.json` 的对应关系见 `reports/diagnostics_details.json` 的 `class_names_consistency`。

## 3. 图像质量（坏图扫描）

- 检查图片数：**7349**（打开 + 结构校验 + 全量解码，耗时 68.98s）
- 发现问题图片：**0**

未发现损坏或无法解码的图片。

## 4. 重复与近重复检查（防泄漏基线）

### 4.1 文件级完全重复（MD5）

- 扫描图片数：7349（耗时 3.92s）
- 完全重复组数：**0**
- 其中跨子集（train/val/test 之间）泄漏组：**0**
- 子集内部重复组：0

结论：不存在跨子集的完全相同文件，与 `prepare_dataset.py` 构建时的断言一致。

### 4.2 感知哈希近重复（pHash）

- 算法：经典 pHash（灰度缩放 + 二维 DCT + 低频 8×8 中位数比特），汉明距离阈值 **≤ 5**
- 成功计算哈希图片数：7349（哈希失败 0 个，耗时 13.39s）
- 候选对校验数：1176763（分块倒排索引，不漏召）
- 近重复图片对数：**45**
- 其中跨子集：**25**

| 距离 | 图片 A | 图片 B | 是否跨子集 |
|---|---|---|---|
| 0 | train/great_pyrenees/`great_pyrenees_173.jpg` | test/great_pyrenees/`great_pyrenees_89.jpg` | 是 |
| 0 | test/japanese_chin/`japanese_chin_194.jpg` | test/japanese_chin/`japanese_chin_79.jpg` | 否 |
| 0 | train/keeshond/`keeshond_140.jpg` | test/keeshond/`keeshond_97.jpg` | 是 |
| 0 | train/Bombay/`Bombay_113.jpg` | train/Bombay/`Bombay_157.jpg` | 否 |
| 0 | train/British_Shorthair/`British_Shorthair_160.jpg` | test/British_Shorthair/`British_Shorthair_278.jpg` | 是 |
| 0 | train/keeshond/`keeshond_175.jpg` | test/keeshond/`keeshond_27.jpg` | 是 |
| 0 | train/keeshond/`keeshond_152.jpg` | test/keeshond/`keeshond_99.jpg` | 是 |
| 0 | train/Abyssinian/`Abyssinian_11.jpg` | train/Abyssinian/`Abyssinian_177.jpg` | 否 |
| 0 | train/leonberger/`leonberger_189.jpg` | test/leonberger/`leonberger_2.jpg` | 是 |
| 0 | train/japanese_chin/`japanese_chin_188.jpg` | test/japanese_chin/`japanese_chin_78.jpg` | 是 |
| 0 | train/keeshond/`keeshond_141.jpg` | test/keeshond/`keeshond_47.jpg` | 是 |
| 0 | train/keeshond/`keeshond_103.jpg` | train/keeshond/`keeshond_167.jpg` | 否 |
| 0 | train/japanese_chin/`japanese_chin_140.jpg` | test/japanese_chin/`japanese_chin_88.jpg` | 是 |
| 0 | train/keeshond/`keeshond_104.jpg` | train/keeshond/`keeshond_170.jpg` | 否 |
| 0 | test/Bombay/`Bombay_38.jpg` | test/Bombay/`Bombay_57.jpg` | 否 |
| 0 | train/german_shorthaired/`german_shorthaired_179.jpg` | test/german_shorthaired/`german_shorthaired_19.jpg` | 是 |
| 0 | test/Birman/`Birman_199.jpg` | test/Birman/`Birman_25.jpg` | 否 |
| 0 | train/Bombay/`Bombay_107.jpg` | train/Bombay/`Bombay_19.jpg` | 否 |
| 0 | train/Abyssinian/`Abyssinian_122.jpg` | train/Abyssinian/`Abyssinian_172.jpg` | 否 |
| 0 | train/german_shorthaired/`german_shorthaired_150.jpg` | test/german_shorthaired/`german_shorthaired_3.jpg` | 是 |

> 该检查为后续 A4「补充现有品种图片」与 V2 扩充建立防泄漏基线：任何新增图片都必须以同样阈值复查，确认与官方 test 集零近重复。

### 4.3 近重复与品种表现的关系（泄漏影响假设）

| 品种 | 涉及近重复对数 | 其中跨子集 | 该品种 F1 |
|---|---|---|---|
| Bombay | 18 | 2 | 0.8865 |
| japanese_chin | 14 | 12 | 0.9388 |
| keeshond | 14 | 10 | 0.9463 |
| Abyssinian | 12 | 2 | 0.7573 |
| german_shorthaired | 6 | 6 | 0.8796 |
| newfoundland | 6 | 4 | 0.8889 |
| British_Shorthair | 4 | 4 | 0.8298 |
| leonberger | 4 | 4 | 0.9447 |
| Egyptian_Mau | 4 | 4 | 0.8663 |
| great_pyrenees | 2 | 2 | 0.8889 |
| Birman | 2 | 0 | 0.6923 |
| scottish_terrier | 2 | 0 | 0.8571 |
| boxer | 2 | 0 | 0.7706 |

- Pearson corr(该品种跨子集近重复数, 该品种 F1) = **0.4807**（n = 37，无近重复记为 0）
- 解读：呈**中等以上正相关**——近重复越多的品种测试 F1 越高。结合跨子集近重复全部同品种（第 4.2 节）这一事实，提示这些品种的测试分数可能被 train/test 视觉重复**抬高**，属于**待验证假设**（需通过剔除泄漏后重评验证）。

**重要披露**：官方 Oxford-IIIT Pet 的 train/test 划分本身存在 25 对跨子集视觉重复（同品种、不同文件）。这不是本项目划分造成的，`prepare_dataset.py` 在构建时已断言 MD5 完全重复为 0。它意味着：**阶段 3 的 0.8035 / 0.8022 基线对这些品种可能偏乐观**，后续实验的对照基线应同时保留“原始口径”与“剔除泄漏口径”两个数字，但**不得**擅自删除官方 test 图片（那会使基线不可比）。

## 5. 基线测试集表现（阶段 3 真实推理，未重跑）

| 指标 | 值 |
|---|---|
| Top-1 Accuracy | 0.8035 |
| Macro-F1 | 0.8022 |
| Weighted-F1 | 0.8026 |
| 测试集图片数 | 3669 |

### 5.1 表现最弱的 10 个品种

| 品种 | Precision | Recall | F1 | test support | train 样本数 |
|---|---|---|---|---|---|
| american_pit_bull_terrier | 0.5833 | 0.4900 | **0.5326** | 100 | 90 |
| staffordshire_bull_terrier | 0.6111 | 0.4944 | **0.5466** | 89 | 90 |
| chihuahua | 0.7391 | 0.5100 | **0.6036** | 100 | 90 |
| Ragdoll | 0.6239 | 0.6800 | **0.6507** | 100 | 90 |
| Birman | 0.6045 | 0.8100 | **0.6923** | 100 | 90 |
| Bengal | 0.6610 | 0.7800 | **0.7156** | 100 | 90 |
| american_bulldog | 0.6780 | 0.8000 | **0.7339** | 100 | 90 |
| wheaten_terrier | 0.8553 | 0.6500 | **0.7386** | 100 | 90 |
| Siamese | 0.9531 | 0.6100 | **0.7439** | 100 | 89 |
| Maine_Coon | 0.7912 | 0.7200 | **0.7539** | 100 | 90 |

### 5.2 表现最强的 5 个品种

| 品种 | Precision | Recall | F1 | test support | train 样本数 |
|---|---|---|---|---|---|
| keeshond | 0.9151 | 0.9798 | 0.9463 | 99 | 90 |
| leonberger | 0.9495 | 0.9400 | 0.9447 | 100 | 90 |
| japanese_chin | 0.9583 | 0.9200 | 0.9388 | 100 | 90 |
| saint_bernard | 0.9200 | 0.9200 | 0.9200 | 100 | 90 |
| samoyed | 0.8661 | 0.9700 | 0.9151 | 100 | 90 |

### 5.3 样本量与 F1 的相关性

- Pearson corr(每类 train 样本数, 每类 F1) = **-0.1824**（n = 37）
- 解读：相关性很弱，说明“哪些类别弱”与“哪些类别样本少”基本无关；错误更可能由品种间外形相似度主导，而每类约 89 张的**绝对量偏小**是整体天花板因素。

## 6. 主要混淆品种对（来自阶段 3 混淆矩阵）

| 真实品种 | 误判为 | 次数 | 该类别正确数 |
|---|---|---|---|
| Siamese | Birman | 26 | 61 |
| american_pit_bull_terrier | staffordshire_bull_terrier | 19 | 49 |
| Birman | Ragdoll | 18 | 81 |
| Ragdoll | Birman | 18 | 68 |
| wheaten_terrier | havanese | 17 | 65 |
| staffordshire_bull_terrier | american_pit_bull_terrier | 16 | 44 |
| chihuahua | Sphynx | 15 | 51 |
| basset_hound | beagle | 14 | 79 |
| Egyptian_Mau | Bengal | 13 | 81 |
| pug | boxer | 13 | 84 |
| Abyssinian | Bengal | 11 | 78 |
| american_pit_bull_terrier | american_bulldog | 11 | 49 |


## 7. 训练过程复核（train_log.csv + experiment_config.json）

| 项目 | 值 |
|---|---|
| 完成 epoch 数 | 10 |
| 最佳 epoch（按 val_acc） | 8 |
| 最佳 val_acc | 0.8401 |
| 末轮 val_acc | 0.8293 |
| 末轮 train_acc | 0.9852 |
| train/val 差距（末轮） | 0.1559 |
| 平均每 epoch 耗时 | 19.73s |
| 训练总耗时 | 197.33s |

- 解读：末轮 train_acc 明显高于 val_acc，差距 0.156，形态更接近**过拟合**而非欠拟合；增加训练轮数的收益需实验验证（A3）。

阶段 2 训练配置要点：

- 架构：resnet18；预训练权重：IMAGENET1K_V1
- 微调方式：full model (backbone not frozen)
- 优化器：AdamW；lr=0.001；weight_decay=0.0001
- 调度器：StepLR(step_size=5, gamma=0.1)
- 损失函数：CrossEntropyLoss
- batch_size=32；epochs=10；image_size=224
- 训练增强：RandomResizedCrop(224, scale=(0.8,1.0)) + RandomHorizontalFlip(0.5) + RandomRotation(10)
- 评估预处理：Resize(256) + CenterCrop(224) + Normalize(ImageNet)

## 8. 既有报告文件时效性核对

- `E:\CatDogBreedNet\reports\split_summary.json` 与真实数据不一致：声明 totals={'train': 27, 'val': 3, 'test': 6}、类别数=3，实际 totals={'train': 3311, 'val': 369, 'test': 3669}、类别数=37。
  - 该文件为早期占位/模板内容，与当前 37 类真实数据不一致；真实统计以重新扫描磁盘的结果与 split_stats.json 为准

## 9. 结论：有证据 vs 待验证

### 有数据支持的结论

1. **无显著类别不平衡**：train 每类 84–90 张（极差仅 6 张），weighted sampling 预期收益小。
2. **数据完整性良好**：7349 张图片全部可正常打开与解码；MD5 跨子集完全重复 0 组。
3. **存在跨子集视觉重复（官方数据固有）**：pHash 阈值 ≤ 5 下共 45 对近重复，其中 **25 对跨子集且全部同品种**（距离 0 的有 39 对）。这是 Oxford-IIIT 官方划分固有的问题，不是本项目划分造成的；`prepare_dataset.py` 构建时已断言 MD5 完全重复为 0。
4. **错误集中于外形近缘品种**：最弱为 american_pit_bull_terrier(0.533)、staffordshire_bull_terrier(0.547)、chihuahua(0.604)；混淆矩阵显示错误集中在少数品种对（见第 6 节）。
5. **低 F1 与样本量基本无关**：Pearson 相关系数仅 -0.182。
6. **标签映射一致**：三个子集类别集合与顺序一致，且与 `artifacts/class_names.json` 完全对应（37 类）。

### 待验证假设（需 A2–A4 实验回答，本报告不下结论）

1. 每类约 89 张的**绝对量偏小**是否为主要天花板（需补充数据实验）。
2. 当前增强策略（RandomResizedCrop + Flip + 轻旋转）是否次优（ColorJitter / RandomErasing / Mixup 的收益）。
3. ResNet18 容量是否不足（ResNet50 / ConvNeXt-Tiny / EfficientNet-B0 对比）。
4. 末轮 train/val 差距所示的过拟合能否通过早停、正则化或分层学习率缓解。
5. 混淆对中是否存在官方标注噪声（需 A5 人工抽样核对）。
6. **跨子集视觉重复是否抬高了相关品种的测试分数**（corr = 0.4807，见第 4.3 节）。验证方式：在保持官方 test 不变的前提下，**额外报告一个“剔除与 train 近重复的 test 子集”指标作为参考口径**，两个口径并列呈现，不替换原基线。

## 10. 交付物与复现方式

- 本报告：`reports/model_diagnostics.md`
- 机器可读明细：`reports/diagnostics_details.json`
- 诊断脚本（只读）：`scripts/diagnose_dataset.py`

```powershell
cd E:\CatDogBreedNet
.venv\Scripts\python.exe scripts\diagnose_dataset.py
```

## 11. 对后续阶段的输入

- **U2（V1.1 实验）**：以第 5–7 节为基线对照；优先验证第 9 节“待验证”清单中的增强策略与 backbone 两项。
- **U3（V2 数据扩充）**：以第 4 节的 pHash 阈值与方法作为新数据防泄漏检查标准；第 6 节混淆对提示新类别应优先补充与现有弱类别区分度高的品种。
- **U5（版本集成）**：第 2 节确认当前标签映射一致，可作为版本切换校验的参照。
