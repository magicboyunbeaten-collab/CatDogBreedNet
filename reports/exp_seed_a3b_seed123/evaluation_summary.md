# 测试集评估报告（阶段 3）

- 评估时间：2026-10-17T05:19:06.361653+00:00
- 权重文件：`E:\CatDogBreedNet\artifacts\exp_seed_a3b_seed123\best_model.pth`（阶段 2 按验证集选择，未使用测试集调参）
- 数据集：Oxford-IIIT Pet Dataset (E:\CatDogBreedNet\data\processed_clean)，官方 test 划分 3669 张，37 类
- 环境：3.11.9 / torch 2.14.1+cu130 / torchvision 0.29.1+cu130 / NVIDIA GeForce RTX 4060 Laptop GPU / Windows-10-10.0.22621-SP0

## 总体指标（真实推理结果）

| 指标 | 值 |
|---|---|
| Top-1 Accuracy | 0.8833 |
| Macro Precision | 0.8860 |
| Macro Recall | 0.8827 |
| **Macro-F1** | **0.8818** |
| Weighted Precision | 0.8871 |
| Weighted Recall | 0.8833 |
| **Weighted-F1** | **0.8826** |

测试样本总数：**3669**（与数据集大小一致，每张图片只评估一次）。

## 表现最好的品种（按 F1）

| 品种 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| japanese_chin | 0.9901 | 1.0000 | 0.9950 | 100 |
| keeshond | 1.0000 | 0.9899 | 0.9949 | 99 |
| leonberger | 1.0000 | 0.9800 | 0.9899 | 100 |
| saint_bernard | 0.9798 | 0.9700 | 0.9749 | 100 |
| pug | 0.9897 | 0.9600 | 0.9746 | 100 |

## 表现最弱的品种（按 F1）

| 品种 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Maine_Coon | 0.9221 | 0.7100 | 0.8023 | 100 |
| Bengal | 0.6812 | 0.9400 | 0.7899 | 100 |
| Ragdoll | 0.7143 | 0.7500 | 0.7317 | 100 |
| staffordshire_bull_terrier | 0.5843 | 0.5843 | 0.5843 | 89 |
| american_pit_bull_terrier | 0.6184 | 0.4700 | 0.5341 | 100 |

## 无预测样本的类别

无——37 个类别在测试集中都至少被预测过一次，`zero_division=0` 未实际生效。

## 推理性能（两个计时口径，不可直接互比）

### 口径 A：模型纯推理（model_only_forward_on_test_tensors）

- 设备：cuda（NVIDIA GeForce RTX 4060 Laptop GPU）
- batch size：32；预热 10 个 batch；计时 20 个 batch；CUDA 同步：True
- 平均单 batch 时间：21.03 ms
- 批处理吞吐：1521.9 images/s
- 单张延迟（batch=1 单独前向，640 次）：平均 2.45 ms / 中位数 1.96 ms / P95 4.22 ms

### 口径 B：端到端（end_to_end_file_to_prediction）

- 包含图片文件读取、PIL 解码、预处理与模型前向；batch size：1；预热 5 张；计时 30 张；CUDA 同步：True
- 单张延迟：平均 5.23 ms / 中位数 3.96 ms / P95 12.83 ms
- 吞吐：191.3 images/s

## 产物文件

- 总体指标 JSON：`E:\CatDogBreedNet\reports\exp_seed_a3b_seed123\test_metrics.json`
- 逐类别分类报告 CSV：`E:\CatDogBreedNet\reports\exp_seed_a3b_seed123\classification_report.csv`
- 混淆矩阵 CSV：`E:\CatDogBreedNet\reports\exp_seed_a3b_seed123\confusion_matrix.csv`
- 混淆矩阵图（计数）：`E:\CatDogBreedNet\reports\exp_seed_a3b_seed123\confusion_matrix.png`
- 混淆矩阵图（行归一化）：`E:\CatDogBreedNet\reports\exp_seed_a3b_seed123\confusion_matrix_normalized.png`
- 推理性能 JSON：`E:\CatDogBreedNet\reports\exp_seed_a3b_seed123\inference_benchmark.json`
- 实验配置（阶段 2）：`E:\CatDogBreedNet\artifacts\experiment_config.json`

## 已知限制

- 以上指标仅反映该基线模型在官方 test 划分上的表现；未做模型对比与增强对比实验；
- Softmax 分数是当前类别集合上的归一化分数，不是真实概率；
- 不保证识别训练类别之外的动物、物体或无效图片。
