# 测试集评估报告（split=test）

- 评估时间：2026-10-18T06:04:01.677283+00:00
- 权重文件：`E:\CatDogBreedNet\artifacts\exp_esp_p10_seed2024\best_model.pth`
- 口径：官方 test 划分，**未**用于训练或模型选择；阶段 2 按验证集选模
- 数据集：Oxford-IIIT Pet Dataset (E:\CatDogBreedNet\data\processed_clean)，`test` 划分 3669 张，37 类
- 环境：3.11.9 / torch 2.14.1+cu130 / torchvision 0.29.1+cu130 / NVIDIA GeForce RTX 4060 Laptop GPU / Windows-10-10.0.22621-SP0

## 总体指标（真实推理结果）

| 指标 | 值 |
|---|---|
| Top-1 Accuracy | 0.8844 |
| Macro Precision | 0.8890 |
| Macro Recall | 0.8841 |
| **Macro-F1** | **0.8830** |
| Weighted Precision | 0.8900 |
| Weighted Recall | 0.8844 |
| **Weighted-F1** | **0.8836** |

测试样本总数：**3669**（与数据集大小一致，每张图片只评估一次）。

## 表现最好的品种（按 F1）

| 品种 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| japanese_chin | 0.9709 | 1.0000 | 0.9852 | 100 |
| leonberger | 0.9899 | 0.9800 | 0.9849 | 100 |
| keeshond | 0.9898 | 0.9798 | 0.9848 | 99 |
| pug | 0.9897 | 0.9600 | 0.9746 | 100 |
| saint_bernard | 0.9697 | 0.9600 | 0.9648 | 100 |

## 表现最弱的品种（按 F1）

| 品种 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Birman | 0.7835 | 0.7600 | 0.7716 | 100 |
| american_bulldog | 0.6992 | 0.8600 | 0.7713 | 100 |
| Ragdoll | 0.7048 | 0.7400 | 0.7220 | 100 |
| staffordshire_bull_terrier | 0.5769 | 0.6742 | 0.6218 | 89 |
| american_pit_bull_terrier | 0.8148 | 0.4400 | 0.5714 | 100 |

## 无预测样本的类别

无——37 个类别在该划分中都至少被预测过一次，`zero_division=0` 未实际生效。

## 推理性能（两个计时口径，不可直接互比）

### 口径 A：模型纯推理（model_only_forward_on_test_tensors）

- 设备：cuda（NVIDIA GeForce RTX 4060 Laptop GPU）
- batch size：32；预热 10 个 batch；计时 20 个 batch；CUDA 同步：True
- 平均单 batch 时间：19.32 ms
- 批处理吞吐：1656.2 images/s
- 单张延迟（batch=1 单独前向，640 次）：平均 2.16 ms / 中位数 1.85 ms / P95 3.92 ms

### 口径 B：端到端（end_to_end_file_to_prediction）

- 包含图片文件读取、PIL 解码、预处理与模型前向；batch size：1；预热 5 张；计时 30 张；CUDA 同步：True
- 单张延迟：平均 5.24 ms / 中位数 3.60 ms / P95 14.56 ms
- 吞吐：190.8 images/s

## 产物文件

- 总体指标 JSON：`E:\CatDogBreedNet\reports\exp_esp_p10_seed2024\test_eval\test_metrics.json`
- 逐类别分类报告 CSV：`E:\CatDogBreedNet\reports\exp_esp_p10_seed2024\test_eval\classification_report.csv`
- 混淆矩阵 CSV：`E:\CatDogBreedNet\reports\exp_esp_p10_seed2024\test_eval\confusion_matrix.csv`
- 混淆矩阵图（计数）：`E:\CatDogBreedNet\reports\exp_esp_p10_seed2024\test_eval\confusion_matrix.png`
- 混淆矩阵图（行归一化）：`E:\CatDogBreedNet\reports\exp_esp_p10_seed2024\test_eval\confusion_matrix_normalized.png`
- 推理性能 JSON：`E:\CatDogBreedNet\reports\exp_esp_p10_seed2024\test_eval\inference_benchmark.json`
- 实验配置（阶段 2）：`E:\CatDogBreedNet\artifacts\experiment_config.json`

## 已知限制

- 以上指标仅反映该权重在官方 test 划分上的表现；test 划分未用于训练或模型选择；
- Softmax 分数是当前类别集合上的归一化分数，不是真实概率；
- 不保证识别训练类别之外的动物、物体或无效图片。
