# 测试集评估报告（阶段 3）

- 评估时间：2026-10-13T10:00:17.488972+00:00
- 权重文件：`E:\CatDogBreedNet\artifacts\best_model.pth`（阶段 2 按验证集选择，未使用测试集调参）
- 数据集：Oxford-IIIT Pet Dataset (E:\CatDogBreedNet\data\processed)，官方 test 划分 3669 张，37 类
- 环境：3.11.9 / torch 2.14.1+cu130 / torchvision 0.29.1+cu130 / NVIDIA GeForce RTX 4060 Laptop GPU / Windows-10-10.0.22621-SP0

## 总体指标（真实推理结果）

| 指标 | 值 |
|---|---|
| Top-1 Accuracy | 0.8035 |
| Macro Precision | 0.8123 |
| Macro Recall | 0.8031 |
| **Macro-F1** | **0.8022** |
| Weighted Precision | 0.8127 |
| Weighted Recall | 0.8035 |
| **Weighted-F1** | **0.8026** |

测试样本总数：**3669**（与数据集大小一致，每张图片只评估一次）。

## 表现最好的品种（按 F1）

| 品种 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| keeshond | 0.9151 | 0.9798 | 0.9463 | 99 |
| leonberger | 0.9495 | 0.9400 | 0.9447 | 100 |
| japanese_chin | 0.9583 | 0.9200 | 0.9388 | 100 |
| saint_bernard | 0.9200 | 0.9200 | 0.9200 | 100 |
| samoyed | 0.8661 | 0.9700 | 0.9151 | 100 |

## 表现最弱的品种（按 F1）

| 品种 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Birman | 0.6045 | 0.8100 | 0.6923 | 100 |
| Ragdoll | 0.6239 | 0.6800 | 0.6507 | 100 |
| chihuahua | 0.7391 | 0.5100 | 0.6036 | 100 |
| staffordshire_bull_terrier | 0.6111 | 0.4944 | 0.5466 | 89 |
| american_pit_bull_terrier | 0.5833 | 0.4900 | 0.5326 | 100 |

## 无预测样本的类别

无——37 个类别在测试集中都至少被预测过一次，`zero_division=0` 未实际生效。

## 推理性能（两个计时口径，不可直接互比）

### 口径 A：模型纯推理（model_only_forward_on_test_tensors）

- 设备：cuda（NVIDIA GeForce RTX 4060 Laptop GPU）
- batch size：32；预热 10 个 batch；计时 50 个 batch；CUDA 同步：True
- 平均单 batch 时间：27.01 ms
- 批处理吞吐：1184.9 images/s
- 单张延迟（batch=1 单独前向，1600 次）：平均 2.95 ms / 中位数 2.20 ms / P95 4.93 ms

### 口径 B：端到端（end_to_end_file_to_prediction）

- 包含图片文件读取、PIL 解码、预处理与模型前向；batch size：1；预热 5 张；计时 100 张；CUDA 同步：True
- 单张延迟：平均 7.18 ms / 中位数 5.78 ms / P95 13.65 ms
- 吞吐：139.2 images/s

## 产物文件

- 总体指标 JSON：`E:\CatDogBreedNet\reports\test_metrics.json`
- 逐类别分类报告 CSV：`E:\CatDogBreedNet\reports\classification_report.csv`
- 混淆矩阵 CSV：`E:\CatDogBreedNet\reports\confusion_matrix.csv`
- 混淆矩阵图（计数）：`E:\CatDogBreedNet\reports\confusion_matrix.png`
- 混淆矩阵图（行归一化）：`E:\CatDogBreedNet\reports\confusion_matrix_normalized.png`
- 推理性能 JSON：`E:\CatDogBreedNet\reports\inference_benchmark.json`
- 实验配置（阶段 2）：`E:\CatDogBreedNet\artifacts\experiment_config.json`

## 易混淆的品种对（来自 confusion_matrix.csv 的真实计数）

| 真实品种 | 被误判为 | 次数 | 该类别正确数 |
|---|---|---|---|
| Siamese | Birman | 26 | 61 |
| american_pit_bull_terrier | staffordshire_bull_terrier | 19 | 49 |
| Ragdoll | Birman | 18 | 68 |
| Birman | Ragdoll | 18 | 81 |
| wheaten_terrier | havanese | 17 | 65 |
| staffordshire_bull_terrier | american_pit_bull_terrier | 16 | 44 |
| chihuahua | Sphynx | 15 | 51 |
| basset_hound | beagle | 14 | 79 |

误判集中在外观相近的品种之间：两种斗牛犬（american_pit_bull_terrier 与
staffordshire_bull_terrier）互混 35 次；三种长毛/重点色猫（Siamese、Birman、
Ragdoll）互混 62 次；短腿猎犬（basset_hound 与 beagle）互混 14 次。

## 已知限制

- 以上指标仅反映该基线模型在官方 test 划分上的表现；未做模型对比与增强对比实验；
- Softmax 分数是当前类别集合上的归一化分数，不是真实概率；
- 不保证识别训练类别之外的动物、物体或无效图片。
