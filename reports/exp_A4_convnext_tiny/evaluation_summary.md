# 测试集评估报告（阶段 3）

- 评估时间：2026-10-17T03:45:58.466886+00:00
- 权重文件：`E:\CatDogBreedNet\artifacts\exp_A4_convnext_tiny\best_model.pth`（阶段 2 按验证集选择，未使用测试集调参）
- 数据集：Oxford-IIIT Pet Dataset (E:\CatDogBreedNet\data\processed)，官方 test 划分 3669 张，37 类
- 环境：3.11.9 / torch 2.14.1+cu130 / torchvision 0.29.1+cu130 / NVIDIA GeForce RTX 4060 Laptop GPU / Windows-10-10.0.22621-SP0

## 总体指标（真实推理结果）

| 指标 | 值 |
|---|---|
| Top-1 Accuracy | 0.6901 |
| Macro Precision | 0.7547 |
| Macro Recall | 0.6894 |
| **Macro-F1** | **0.6800** |
| Weighted Precision | 0.7545 |
| Weighted Recall | 0.6901 |
| **Weighted-F1** | **0.6802** |

测试样本总数：**3669**（与数据集大小一致，每张图片只评估一次）。

## 表现最好的品种（按 F1）

| 品种 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| scottish_terrier | 0.8125 | 0.9192 | 0.8626 | 99 |
| great_pyrenees | 0.8148 | 0.8800 | 0.8462 | 100 |
| Bombay | 0.8471 | 0.8182 | 0.8324 | 88 |
| german_shorthaired | 0.9359 | 0.7300 | 0.8202 | 100 |
| pomeranian | 0.8000 | 0.8400 | 0.8195 | 100 |

## 表现最弱的品种（按 F1）

| 品种 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| saint_bernard | 1.0000 | 0.3200 | 0.4848 | 100 |
| staffordshire_bull_terrier | 0.6667 | 0.3596 | 0.4672 | 89 |
| Ragdoll | 0.6667 | 0.3200 | 0.4324 | 100 |
| boxer | 0.9032 | 0.2828 | 0.4308 | 99 |
| beagle | 0.7941 | 0.2700 | 0.4030 | 100 |

## 无预测样本的类别

无——37 个类别在测试集中都至少被预测过一次，`zero_division=0` 未实际生效。

## 推理性能（两个计时口径，不可直接互比）

### 口径 A：模型纯推理（model_only_forward_on_test_tensors）

- 设备：cuda（NVIDIA GeForce RTX 4060 Laptop GPU）
- batch size：32；预热 10 个 batch；计时 20 个 batch；CUDA 同步：True
- 平均单 batch 时间：62.51 ms
- 批处理吞吐：511.9 images/s
- 单张延迟（batch=1 单独前向，640 次）：平均 4.51 ms / 中位数 4.02 ms / P95 8.05 ms

### 口径 B：端到端（end_to_end_file_to_prediction）

- 包含图片文件读取、PIL 解码、预处理与模型前向；batch size：1；预热 5 张；计时 30 张；CUDA 同步：True
- 单张延迟：平均 9.03 ms / 中位数 7.66 ms / P95 16.32 ms
- 吞吐：110.7 images/s

## 产物文件

- 总体指标 JSON：`E:\CatDogBreedNet\reports\exp_A4_convnext_tiny\test_metrics.json`
- 逐类别分类报告 CSV：`E:\CatDogBreedNet\reports\exp_A4_convnext_tiny\classification_report.csv`
- 混淆矩阵 CSV：`E:\CatDogBreedNet\reports\exp_A4_convnext_tiny\confusion_matrix.csv`
- 混淆矩阵图（计数）：`E:\CatDogBreedNet\reports\exp_A4_convnext_tiny\confusion_matrix.png`
- 混淆矩阵图（行归一化）：`E:\CatDogBreedNet\reports\exp_A4_convnext_tiny\confusion_matrix_normalized.png`
- 推理性能 JSON：`E:\CatDogBreedNet\reports\exp_A4_convnext_tiny\inference_benchmark.json`
- 实验配置（阶段 2）：`E:\CatDogBreedNet\artifacts\experiment_config.json`

## 已知限制

- 以上指标仅反映该基线模型在官方 test 划分上的表现；未做模型对比与增强对比实验；
- Softmax 分数是当前类别集合上的归一化分数，不是真实概率；
- 不保证识别训练类别之外的动物、物体或无效图片。
