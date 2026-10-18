# 测试集评估报告（split=test）

- 评估时间：2026-10-18T06:04:28.773003+00:00
- 权重文件：`E:\CatDogBreedNet\artifacts\exp_esp_p10_seed7\best_model.pth`
- 口径：官方 test 划分，**未**用于训练或模型选择；阶段 2 按验证集选模
- 数据集：Oxford-IIIT Pet Dataset (E:\CatDogBreedNet\data\processed_clean)，`test` 划分 3669 张，37 类
- 环境：3.11.9 / torch 2.14.1+cu130 / torchvision 0.29.1+cu130 / NVIDIA GeForce RTX 4060 Laptop GPU / Windows-10-10.0.22621-SP0

## 总体指标（真实推理结果）

| 指标 | 值 |
|---|---|
| Top-1 Accuracy | 0.8883 |
| Macro Precision | 0.8929 |
| Macro Recall | 0.8879 |
| **Macro-F1** | **0.8867** |
| Weighted Precision | 0.8938 |
| Weighted Recall | 0.8883 |
| **Weighted-F1** | **0.8874** |

测试样本总数：**3669**（与数据集大小一致，每张图片只评估一次）。

## 表现最好的品种（按 F1）

| 品种 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| japanese_chin | 0.9900 | 0.9900 | 0.9900 | 100 |
| newfoundland | 0.9900 | 0.9900 | 0.9900 | 100 |
| keeshond | 0.9898 | 0.9798 | 0.9848 | 99 |
| leonberger | 0.9706 | 0.9900 | 0.9802 | 100 |
| yorkshire_terrier | 0.9898 | 0.9700 | 0.9798 | 100 |

## 表现最弱的品种（按 F1）

| 品种 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| american_bulldog | 0.6794 | 0.8900 | 0.7706 | 100 |
| Bengal | 0.6522 | 0.9000 | 0.7563 | 100 |
| Ragdoll | 0.6857 | 0.7200 | 0.7024 | 100 |
| staffordshire_bull_terrier | 0.6316 | 0.6742 | 0.6522 | 89 |
| american_pit_bull_terrier | 0.8113 | 0.4300 | 0.5621 | 100 |

## 无预测样本的类别

无——37 个类别在该划分中都至少被预测过一次，`zero_division=0` 未实际生效。

## 推理性能（两个计时口径，不可直接互比）

### 口径 A：模型纯推理（model_only_forward_on_test_tensors）

- 设备：cuda（NVIDIA GeForce RTX 4060 Laptop GPU）
- batch size：32；预热 10 个 batch；计时 20 个 batch；CUDA 同步：True
- 平均单 batch 时间：20.83 ms
- 批处理吞吐：1536.1 images/s
- 单张延迟（batch=1 单独前向，640 次）：平均 2.36 ms / 中位数 1.92 ms / P95 4.01 ms

### 口径 B：端到端（end_to_end_file_to_prediction）

- 包含图片文件读取、PIL 解码、预处理与模型前向；batch size：1；预热 5 张；计时 30 张；CUDA 同步：True
- 单张延迟：平均 4.86 ms / 中位数 3.64 ms / P95 12.51 ms
- 吞吐：205.6 images/s

## 产物文件

- 总体指标 JSON：`E:\CatDogBreedNet\reports\exp_esp_p10_seed7\test_eval\test_metrics.json`
- 逐类别分类报告 CSV：`E:\CatDogBreedNet\reports\exp_esp_p10_seed7\test_eval\classification_report.csv`
- 混淆矩阵 CSV：`E:\CatDogBreedNet\reports\exp_esp_p10_seed7\test_eval\confusion_matrix.csv`
- 混淆矩阵图（计数）：`E:\CatDogBreedNet\reports\exp_esp_p10_seed7\test_eval\confusion_matrix.png`
- 混淆矩阵图（行归一化）：`E:\CatDogBreedNet\reports\exp_esp_p10_seed7\test_eval\confusion_matrix_normalized.png`
- 推理性能 JSON：`E:\CatDogBreedNet\reports\exp_esp_p10_seed7\test_eval\inference_benchmark.json`
- 实验配置（阶段 2）：`E:\CatDogBreedNet\artifacts\experiment_config.json`

## 已知限制

- 以上指标仅反映该权重在官方 test 划分上的表现；test 划分未用于训练或模型选择；
- Softmax 分数是当前类别集合上的归一化分数，不是真实概率；
- 不保证识别训练类别之外的动物、物体或无效图片。
