# 测试集评估报告（阶段 3）

- 评估时间：2026-10-17T03:19:55.625096+00:00
- 权重文件：`E:\CatDogBreedNet\artifacts\exp_A3c_label_smoothing\best_model.pth`（阶段 2 按验证集选择，未使用测试集调参）
- 数据集：Oxford-IIIT Pet Dataset (E:\CatDogBreedNet\data\processed)，官方 test 划分 3669 张，37 类
- 环境：3.11.9 / torch 2.14.1+cu130 / torchvision 0.29.1+cu130 / NVIDIA GeForce RTX 4060 Laptop GPU / Windows-10-10.0.22621-SP0

## 总体指标（真实推理结果）

| 指标 | 值 |
|---|---|
| Top-1 Accuracy | 0.8204 |
| Macro Precision | 0.8253 |
| Macro Recall | 0.8198 |
| **Macro-F1** | **0.8188** |
| Weighted Precision | 0.8259 |
| Weighted Recall | 0.8204 |
| **Weighted-F1** | **0.8193** |

测试样本总数：**3669**（与数据集大小一致，每张图片只评估一次）。

## 表现最好的品种（按 F1）

| 品种 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| keeshond | 0.9406 | 0.9596 | 0.9500 | 99 |
| pug | 0.9495 | 0.9400 | 0.9447 | 100 |
| samoyed | 0.9135 | 0.9500 | 0.9314 | 100 |
| leonberger | 0.9674 | 0.8900 | 0.9271 | 100 |
| japanese_chin | 0.9038 | 0.9400 | 0.9216 | 100 |

## 表现最弱的品种（按 F1）

| 品种 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| chihuahua | 0.8182 | 0.6300 | 0.7119 | 100 |
| Ragdoll | 0.6923 | 0.7200 | 0.7059 | 100 |
| american_bulldog | 0.6727 | 0.7400 | 0.7048 | 100 |
| staffordshire_bull_terrier | 0.6111 | 0.4944 | 0.5466 | 89 |
| american_pit_bull_terrier | 0.5443 | 0.4300 | 0.4804 | 100 |

## 无预测样本的类别

无——37 个类别在测试集中都至少被预测过一次，`zero_division=0` 未实际生效。

## 推理性能（两个计时口径，不可直接互比）

### 口径 A：模型纯推理（model_only_forward_on_test_tensors）

- 设备：cuda（NVIDIA GeForce RTX 4060 Laptop GPU）
- batch size：32；预热 10 个 batch；计时 20 个 batch；CUDA 同步：True
- 平均单 batch 时间：23.21 ms
- 批处理吞吐：1379.0 images/s
- 单张延迟（batch=1 单独前向，640 次）：平均 2.31 ms / 中位数 2.00 ms / P95 4.01 ms

### 口径 B：端到端（end_to_end_file_to_prediction）

- 包含图片文件读取、PIL 解码、预处理与模型前向；batch size：1；预热 5 张；计时 30 张；CUDA 同步：True
- 单张延迟：平均 5.54 ms / 中位数 3.90 ms / P95 13.16 ms
- 吞吐：180.4 images/s

## 产物文件

- 总体指标 JSON：`E:\CatDogBreedNet\reports\exp_A3c_label_smoothing\test_metrics.json`
- 逐类别分类报告 CSV：`E:\CatDogBreedNet\reports\exp_A3c_label_smoothing\classification_report.csv`
- 混淆矩阵 CSV：`E:\CatDogBreedNet\reports\exp_A3c_label_smoothing\confusion_matrix.csv`
- 混淆矩阵图（计数）：`E:\CatDogBreedNet\reports\exp_A3c_label_smoothing\confusion_matrix.png`
- 混淆矩阵图（行归一化）：`E:\CatDogBreedNet\reports\exp_A3c_label_smoothing\confusion_matrix_normalized.png`
- 推理性能 JSON：`E:\CatDogBreedNet\reports\exp_A3c_label_smoothing\inference_benchmark.json`
- 实验配置（阶段 2）：`E:\CatDogBreedNet\artifacts\experiment_config.json`

## 已知限制

- 以上指标仅反映该基线模型在官方 test 划分上的表现；未做模型对比与增强对比实验；
- Softmax 分数是当前类别集合上的归一化分数，不是真实概率；
- 不保证识别训练类别之外的动物、物体或无效图片。
