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

## 已知限制

- 验证精度 0.84 为基线水平；尚未做模型对比（MobileNetV3 等）与增强对比实验；
- Softmax 分数是当前类别集合上的归一化分数，不是真实概率；
- 不保证识别训练类别之外的动物或物体。
