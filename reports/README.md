# 实验报告索引

本目录保存论文/答辩所需的真实实验材料。所有数字均来自实际运行，可追溯到
`artifacts/experiment_config.json` 与训练日志。

## 数据集

- [`dataset.md`](dataset.md)：来源、许可原文、引用、划分方案、37 类统计

## 实验 1：ResNet18 基线（2026-10-13，已完成）

| 项目 | 值 |
|---|---|
| 模型 | torchvision ResNet18，ImageNet V1 预训练权重，全模型微调 |
| 数据 | Oxford-IIIT Pet，37 类；train 3311 / val 369 / test 3669（官方 test 作测试集） |
| 超参数 | AdamW(lr=1e-3, weight_decay=1e-4)，StepLR(step=5, gamma=0.1)，CrossEntropyLoss，batch 32，10 epochs，种子 42 |
| 训练环境 | RTX 4060 Laptop 8GB，torch 2.14.1+cu130，10 epochs 共 198.8s（约 19.9s/epoch） |
| 最佳验证精度 | **0.8401**（epoch 8，按验证集选择，未使用测试集调参） |
| 最终 epoch | train_acc 0.9852 / val_acc 0.8293（epoch 10） |

逐轮指标见 `train_log.csv`（由 `.gitignore` 排除，仅本机留存），曲线见
`loss_curve.png` / `accuracy_curve.png`（同样仅本机留存）。完整超参数与环境
记录在 `artifacts/experiment_config.json`（已提交 Git）。

### 单图预测抽样（真实测试图片，Top-1 全部正确）

| 真实标签 | 预测 Top-1 | 分数 |
|---|---|---|
| Siamese | Siamese | 0.9653 |
| Bengal | Bengal | 0.8569 |
| beagle | beagle | 0.9795 |
| pug | pug | 1.0000 |
| samoyed | samoyed | 0.9989 |
| boxer | boxer | 0.9985 |

抽样方式：每个品种取测试集第一张图片，命令
`python -m ml.predict --image <图片> --top-k 3`。测试集整体指标（Accuracy、
Macro-F1、混淆矩阵）属于阶段 3 范围，尚未计算。

## 实验 1 补充：完整测试集评估（2026-10-13，阶段 3 完成）

对 `best_model.pth` 在**完整官方 test 集 3669 张**上重新推理（每张只评估一次，
未用测试集调参）：

| 指标 | 值 |
|---|---|
| Top-1 Accuracy | 0.8035 |
| Macro Precision / Recall / **F1** | 0.8123 / 0.8031 / **0.8022** |
| Weighted Precision / Recall / **F1** | 0.8127 / 0.8035 / **0.8026** |

- 37 个类别均至少被预测过一次，`zero_division=0` 未实际生效（策略已在
  `test_metrics.json` 中说明）。
- 最好：keeshond F1 0.946、leonberger 0.945、japanese_chin 0.939；
  最弱：american_pit_bull_terrier 0.533、staffordshire_bull_terrier 0.547。
- 误判集中在近缘品种：两种斗牛犬互混 35 次；Siamese/Birman/Ragdoll 互混 62 次。

推理性能（RTX 4060，torch 2.14.1+cu130，两个口径不可互比）：

| 口径 | 内容 | 结果 |
|---|---|---|
| 模型纯推理 | batch 32，预热 10 + 计时 50 batch，CUDA 同步 | 27.01 ms/batch，1184.9 img/s；单张平均 2.95 / 中位 2.20 / P95 4.93 ms（1600 次） |
| 端到端 | 含文件读取+PIL 解码+预处理，batch 1，100 张 | 平均 7.18 / 中位 5.78 / P95 13.65 ms，139.2 img/s |

产物：`test_metrics.json`、`classification_report.csv`、`confusion_matrix.csv`、
`confusion_matrix.png`、`confusion_matrix_normalized.png`、
`inference_benchmark.json`、`evaluation_summary.md`（详见该报告）。
复现命令：`python -m ml.evaluate`。

## 已知限制

- 验证精度 0.84 为基线水平；尚未做模型对比（MobileNetV3 等）与增强对比实验；
- Softmax 分数是当前类别集合上的归一化分数，不是真实概率；
- 不保证识别训练类别之外的动物或物体。
