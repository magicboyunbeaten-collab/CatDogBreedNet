# 测试集评估报告（阶段 3）

- 评估时间：2026-10-17T03:41:23.769502+00:00
- 权重文件：`E:\CatDogBreedNet\artifacts\exp_A4_resnet50\best_model.pth`（阶段 2 按验证集选择，未使用测试集调参）
- 数据集：Oxford-IIIT Pet Dataset (E:\CatDogBreedNet\data\processed)，官方 test 划分 3669 张，37 类
- 环境：3.11.9 / torch 2.14.1+cu130 / torchvision 0.29.1+cu130 / NVIDIA GeForce RTX 4060 Laptop GPU / Windows-10-10.0.22621-SP0

## 总体指标（真实推理结果）

| 指标 | 值 |
|---|---|
| Top-1 Accuracy | 0.2537 |
| Macro Precision | 0.2571 |
| Macro Recall | 0.2550 |
| **Macro-F1** | **0.2305** |
| Weighted Precision | 0.2572 |
| Weighted Recall | 0.2537 |
| **Weighted-F1** | **0.2300** |

测试样本总数：**3669**（与数据集大小一致，每张图片只评估一次）。

## 表现最好的品种（按 F1）

| 品种 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Egyptian_Mau | 0.4260 | 0.7423 | 0.5414 | 97 |
| newfoundland | 0.4483 | 0.3900 | 0.4171 | 100 |
| Russian_Blue | 0.3472 | 0.5000 | 0.4098 | 100 |
| Bombay | 0.2826 | 0.5909 | 0.3824 | 88 |
| Bengal | 0.3936 | 0.3700 | 0.3814 | 100 |

## 表现最弱的品种（按 F1）

| 品种 | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| english_setter | 0.2632 | 0.0500 | 0.0840 | 100 |
| english_cocker_spaniel | 0.2174 | 0.0500 | 0.0813 | 100 |
| boxer | 0.3000 | 0.0303 | 0.0550 | 99 |
| Maine_Coon | 0.0435 | 0.0300 | 0.0355 | 100 |
| american_pit_bull_terrier | 0.0000 | 0.0000 | 0.0000 | 100 |

## 无预测样本的类别

无——37 个类别在测试集中都至少被预测过一次，`zero_division=0` 未实际生效。

## 推理性能（两个计时口径，不可直接互比）

### 口径 A：模型纯推理（model_only_forward_on_test_tensors）

- 设备：cuda（NVIDIA GeForce RTX 4060 Laptop GPU）
- batch size：32；预热 10 个 batch；计时 20 个 batch；CUDA 同步：True
- 平均单 batch 时间：62.30 ms
- 批处理吞吐：513.6 images/s
- 单张延迟（batch=1 单独前向，640 次）：平均 5.44 ms / 中位数 4.58 ms / P95 9.67 ms

### 口径 B：端到端（end_to_end_file_to_prediction）

- 包含图片文件读取、PIL 解码、预处理与模型前向；batch size：1；预热 5 张；计时 30 张；CUDA 同步：True
- 单张延迟：平均 8.50 ms / 中位数 7.11 ms / P95 16.76 ms
- 吞吐：117.6 images/s

## 产物文件

- 总体指标 JSON：`E:\CatDogBreedNet\reports\exp_A4_resnet50\test_metrics.json`
- 逐类别分类报告 CSV：`E:\CatDogBreedNet\reports\exp_A4_resnet50\classification_report.csv`
- 混淆矩阵 CSV：`E:\CatDogBreedNet\reports\exp_A4_resnet50\confusion_matrix.csv`
- 混淆矩阵图（计数）：`E:\CatDogBreedNet\reports\exp_A4_resnet50\confusion_matrix.png`
- 混淆矩阵图（行归一化）：`E:\CatDogBreedNet\reports\exp_A4_resnet50\confusion_matrix_normalized.png`
- 推理性能 JSON：`E:\CatDogBreedNet\reports\exp_A4_resnet50\inference_benchmark.json`
- 实验配置（阶段 2）：`E:\CatDogBreedNet\artifacts\experiment_config.json`

## 已知限制

- 以上指标仅反映该基线模型在官方 test 划分上的表现；未做模型对比与增强对比实验；
- Softmax 分数是当前类别集合上的归一化分数，不是真实概率；
- 不保证识别训练类别之外的动物、物体或无效图片。
