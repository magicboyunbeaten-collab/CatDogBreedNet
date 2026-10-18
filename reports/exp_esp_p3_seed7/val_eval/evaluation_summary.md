# 验证集评估报告（split=val）

- 评估时间：2026-10-18T04:56:11.832495+00:00
- 权重文件：`E:\CatDogBreedNet\artifacts\exp_esp_p3_seed7\best_model.pth`
- 口径：**验证集**指标，用于模型/策略选择；与最终测试集指标必须分开解读
- 数据集：Oxford-IIIT Pet Dataset (E:\CatDogBreedNet\data\processed_clean)，`val` 划分 368 张，37 类
- 环境：3.11.9 / torch 2.14.1+cu130 / torchvision 0.29.1+cu130 / NVIDIA GeForce RTX 4060 Laptop GPU / Windows-10-10.0.22621-SP0

## 总体指标（真实推理结果）

| 指标 | 值 |
|---|---|
| Top-1 Accuracy | 0.8967 |
| Macro Precision | 0.9052 |
| Macro Recall | 0.8967 |
| **Macro-F1** | **0.8964** |
| Weighted Precision | 0.9052 |
| Weighted Recall | 0.8967 |
| **Weighted-F1** | **0.8965** |

测试样本总数：**368**（与数据集大小一致，每张图片只评估一次）。

## 表现最好的品种（按 F1）

| 品种 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Bombay | 1.0000 | 1.0000 | 1.0000 | 10 |
| Sphynx | 1.0000 | 1.0000 | 1.0000 | 10 |
| german_shorthaired | 1.0000 | 1.0000 | 1.0000 | 10 |
| havanese | 1.0000 | 1.0000 | 1.0000 | 10 |
| japanese_chin | 1.0000 | 1.0000 | 1.0000 | 10 |

## 表现最弱的品种（按 F1）

| 品种 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| boxer | 0.6429 | 0.9000 | 0.7500 | 10 |
| american_bulldog | 0.7778 | 0.7000 | 0.7368 | 10 |
| Ragdoll | 0.6154 | 0.8000 | 0.6957 | 10 |
| staffordshire_bull_terrier | 0.6667 | 0.6000 | 0.6316 | 10 |
| Birman | 0.6250 | 0.5000 | 0.5556 | 10 |

## 无预测样本的类别

无——37 个类别在该划分中都至少被预测过一次，`zero_division=0` 未实际生效。

## 推理性能

- 本次以 `--no-benchmark` 运行，未做推理计时；上方指标仍为真实推理结果。

## 产物文件

- 总体指标 JSON：`E:\CatDogBreedNet\reports\exp_esp_p3_seed7\val_eval\test_metrics.json`
- 逐类别分类报告 CSV：`E:\CatDogBreedNet\reports\exp_esp_p3_seed7\val_eval\classification_report.csv`
- 混淆矩阵 CSV：`E:\CatDogBreedNet\reports\exp_esp_p3_seed7\val_eval\confusion_matrix.csv`
- 混淆矩阵图（计数）：`E:\CatDogBreedNet\reports\exp_esp_p3_seed7\val_eval\confusion_matrix.png`
- 混淆矩阵图（行归一化）：`E:\CatDogBreedNet\reports\exp_esp_p3_seed7\val_eval\confusion_matrix_normalized.png`
- 推理性能 JSON：`E:\CatDogBreedNet\reports\exp_esp_p3_seed7\val_eval\inference_benchmark.json`
- 实验配置（阶段 2）：`E:\CatDogBreedNet\artifacts\experiment_config.json`

## 已知限制

- 以上指标仅反映该权重在 **验证集（split=val）**划分上的表现；该划分**不能**替代官方 test 集的最终评估；
- Softmax 分数是当前类别集合上的归一化分数，不是真实概率；
- 不保证识别训练类别之外的动物、物体或无效图片。
