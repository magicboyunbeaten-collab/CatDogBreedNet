# 模型改进计划：错误率与训练数据不足诊断

> 生成日期：2026-10-14
> 诊断对象：阶段 2 训练的 ResNet18 基线（`artifacts/best_model.pth`，37 类）
> 本文档**只做诊断与计划**，未重新训练、未修改任何权重与基线评估报告。
> 文中所有数字均来自本机实测；未来实验的预期效果一律标注为"目标/待验证"。

## 1. 当前基线（真实结果，作为唯一对照）

| 项目 | 值 | 来源 |
|---|---|---|
| 最佳验证集准确率 | 0.8401（epoch 8 / 10） | 阶段 2 训练日志 |
| 测试集 Top-1 Accuracy | 0.8035 | 阶段 3 完整评估（3669 张） |
| 测试集 Macro-F1 | 0.8022 | 同上 |
| 测试集 Weighted-F1 | 0.8026 | 同上 |
| 训练配置 | ResNet18 + IMAGENET1K_V1，AdamW lr=1e-3，batch 32，10 epochs | `artifacts/experiment_config.json` |

**规则：官方 test 划分（3669 张）保持冻结，作为所有后续实验的唯一最终对照；
任何实验按验证集（369 张）选模，禁止依据测试集反复调参。**

## 2. 数据集真实统计（2026-10-14 重新统计）

| 子集 | 总数 | 每类最少 | 每类最多 | 每类均值 |
|---|---|---|---|---|
| train | 3311 | 84（Egyptian_Mau） | 90 | 89.5 |
| val | 369 | 9 | 10 | 9.97 |
| test | 3669 | 88 | 100 | 99.2 |

每类训练样本明细（按 train 数升序，前 8 类）：

| 品种 | train | val | test |
|---|---|---|---|
| Egyptian_Mau | 84 | 9 | 97 |
| Bombay | 86 | 10 | 88 |
| english_cocker_spaniel | 86 | 10 | 100 |
| newfoundland | 86 | 10 | 100 |
| Siamese | 89 | 10 | 100 |
| 其余 32 类 | 90 | 10 | 88–100 |

**结论：37 类样本量几乎均匀（84–90），不存在有证据的类别不平衡问题。**
"训练数据不足"体现为**每类绝对量小（均值 89.5 张）**，而非类别间不均。

## 3. 逐品种表现（来自 `reports/classification_report.csv` 真实推理）

**最弱的 10 个品种（F1）：**

| 品种 | F1 | Precision | Recall | test support | train 数 |
|---|---|---|---|---|---|
| american_pit_bull_terrier | 0.533 | 0.657 | 0.450 | 100 | 90 |
| staffordshire_bull_terrier | 0.547 | 0.614 | 0.494 | 89 | 90 |
| chihuahua | 0.604 | 0.672 | 0.550 | 100 | 90 |
| Ragdoll | 0.651 | 0.696 | 0.610 | 100 | 90 |
| Birman | 0.692 | 0.698 | 0.686 | 100 | 90 |
| Bengal | 0.716 | 0.735 | 0.700 | 100 | 90 |
| american_bulldog | 0.734 | 0.780 | 0.700 | 100 | 90 |
| wheaten_terrier | 0.739 | 0.768 | 0.715 | 100 | 90 |
| Siamese | 0.744 | 0.729 | 0.760 | 100 | 89 |
| Maine_Coon | 0.754 | 0.783 | 0.730 | 100 | 90 |

**最强的 5 个品种（F1）**：keeshond 0.946、leonberger 0.945、japanese_chin 0.939、
saint_bernard 0.920、samoyed 0.915。

## 4. 易混淆品种对（来自 `reports/confusion_matrix.csv` 真实计数）

| 真实品种 | 误判为 | 次数 | 该类别正确数 |
|---|---|---|---|
| Siamese | Birman | 26 | 61 |
| american_pit_bull_terrier | staffordshire_bull_terrier | 19 | 49 |
| Ragdoll | Birman | 18 | 68 |
| Birman | Ragdoll | 18 | 81 |
| wheaten_terrier | havanese | 17 | 65 |
| staffordshire_bull_terrier | american_pit_bull_terrier | 16 | 44 |
| chihuahua | Sphynx（无毛猫） | 15 | 51 |
| basset_hound | beagle | 14 | 79 |

聚集特征：两种斗牛犬互混 35 次；三种重点色长毛猫（Siamese/Birman/Ragdoll）互混 62 次。

## 5. 原因分析（区分"有证据"与"待验证"）

| 假设 | 证据状态 | 说明 |
|---|---|---|
| 每类绝对训练量小（约 89 张）限制细粒度判别 | **有间接证据** | 最强品种（keeshond/leonberger 等）外观特征独特；最弱品种均为外形高度相似的近缘种。样本量与 F1 的 Pearson 相关系数仅 -0.182（弱负相关，n=37），说明"哪个类弱"与"哪个类样本少"基本无关——错误由品种间相似度主导，样本量是整体天花板因素 |
| 品种间视觉相似度是主要错误来源 | **有证据** | 混淆矩阵显示错误集中在近缘品种对（§4） |
| 类别不平衡 | **无证据（基本排除）** | 每类 84–90 张，无显著不平衡；weighted sampling 预期收益小 |
| 数据增强策略不当 | **待验证** | 当前增强为 RandomResizedCrop + 水平翻转 + 轻旋转；未实验 ColorJitter/RandomErasing/Mixup，需对照实验 |
| 模型容量/预训练权重不适配 | **待验证** | ResNet18 为最小 backbone 之一；更大 backbone（ResNet50/ConvNeXt-Tiny）在 8GB 显存可跑，需对照实验 |
| 训练轮数不足/欠拟合 | **部分有证据** | 末轮 train_acc 0.9852 vs val_acc 0.8293 存在差距，但更符合过拟合特征而非欠拟合；增加 epochs 收益待验证 |

## 6. 改进方案 A：改善现有 37 类准确率（按优先级）

> 所有实验共用同一验证集选模规则；每个实验独立目录存放产物，不覆盖基线。

### A1（P0）定向补充低表现品种的许可合规图像
- 目标品种：american_pit_bull_terrier、staffordshire_bull_terrier、chihuahua、
  Ragdoll、Birman、Bengal、american_bulldog、wheaten_terrier、Siamese、Maine_Coon。
- 数据源候选（**均需许可核查后方可使用**）：
  - Oxford-IIIT Pet 官方扩展（若有新版本发布）；
  - 其他公开猫狗品种数据集（使用前逐源核对许可证与再分发条款）；
  - 自行拍摄/众包标注（许可最清晰，成本最高）。
- 去重与防泄漏（强制）：
  1. 与现有 train/val/test 全部图像做文件哈希（MD5）比对，剔除完全重复；
  2. 感知哈希（pHash，汉明距离阈值，如 ≤5 视为近重复）剔除近重复；
  3. 新增数据中**任何**与官方 test 集近相似的图像一律剔除，宁可漏不可漏；
  4. 去重报告存档，列出剔除数量与原因。
- 验收指标：Macro-F1 相对基线 0.8022 提升 ≥ 0.02，且最弱品种 F1 ≥ 0.60；
  补充后每类 train ≥ 150 张时重训对比。
- 预计交付：扩充后的 data 索引、去重报告、新 `best_model.pth`、新的分类报告与混淆矩阵。

### A2（P0）数据增强对照实验
- 固定模型/优化器/epochs，仅改变增强：
  - E2a（现状）：RandomResizedCrop + Flip + 轻旋转；
  - E2b：+ ColorJitter(0.2, 0.2, 0.2)；
  - E2c：+ RandomErasing(p=0.25)；
  - E2d：Mixup(α=0.2) 或 CutMix（训练时实现，评估不变）。
- 验收：val 选模后 test 只评一次；任一方案 Macro-F1 ≥ 基线 + 0.01 即记录为有效。
- 注意：增强只用于 train；val/test 保持确定性预处理（与现有一致）。

### A3（P1）微调策略对照实验
- E3a：解冻 layer4，lr 5e-4（现为全网络 lr 1e-3 同步训练）；
- E3b：分层学习率（head 1e-3 / layer4 5e-4 / 其余 1e-4）；
- E3c：label smoothing 0.1；
- E3d：epochs 10 → 20 + early stop（按 val_acc  patience 3）。
- 验收：相对基线 Macro-F1 ≥ +0.01；训练时长增幅可接受（当前 10 epochs 约 199s）。

### A4（P1）预训练 backbone 对比
- 候选：ResNet50、ConvNeXt-Tiny、EfficientNet-B0（类别数仍为 37）。
- 约束：RTX 4060 Laptop 8GB；batch 相应下调（如 16），记录显存峰值。
- 验收：Macro-F1 ≥ 基线 + 0.02 且单张推理耗时（口径同阶段 3）增幅 ≤ 50%。

### A5（P2）难例分析与定向数据清洗
- 对 §4 的 8 个混淆对抽样人工检查（每对 20 张），确认是标注噪声还是真实相似；
- 若发现 Oxford 官方标注错误，记录 case 列表（不修改官方 test 标注）。

## 7. 改进方案 B：新增品种类别（如边境牧羊犬 Border Collie）

> 这是与方案 A 不同的任务：类别数将从 37 增至 38+，模型必须重新训练。

1. **数据需求**：新类别图像（许可合规）、与现有 37 类的区分度评估（人工抽检）。
2. **防泄漏**：新类别图像同样执行 A1 的哈希 + pHash + 近重复检查，
   确保与现有 test 3669 张零重叠。
3. **类别映射**：`artifacts/class_names.json` 扩展为 38 类（保持原 37 类顺序，
   新类追加；数据库历史记录不受影响，`breedNames.js` 需补中文映射）。
4. **划分规则**：新类别按 90/10 划分 train/val（种子 42，与现有一致）；
   **官方 test 集不加入新类别图像**（保持基线对照有效性）——这意味着测试集
   暂时无法评估新类别，需在报告中明确说明；或在确认无泄漏后，将新类别测试图
   作为独立的"新类别测试子集"单独报告。
5. **训练与验证**：从基线权重微调（冻结策略同 A3a）或从头训练；val 选模。
6. **验收指标**：新类别测试集 Recall ≥ 0.80；原 37 类 Macro-F1 下降 ≤ 0.02
   （灾难性遗忘检查）；混淆矩阵中新类别与外形相近犬种（如 australian_shepherd
   如已存在，否则最相近犬种）的互混次数单独统计。

## 8. 实验管理规则

1. 所有实验产物按 `artifacts/exp_<编号>_<日期>/` 独立存放，不覆盖 `best_model.pth`；
2. 每个实验保存完整 `experiment_config.json`（含增强、数据版本、随机种子）；
3. 测试集评估每个实验只做一次并记录，报告须注明"test 仅最终评估用途"；
4. 数据扩充必须附去重报告；无法证明无泄漏的数据不得进入训练；
5. 任何声称的提升必须附 `ml.evaluate` 真实输出，禁止手工填写指标。

## 9. 预计交付物汇总

| 实验 | 交付物 |
|---|---|
| A1 | 扩充数据索引、去重报告、新权重、新分类报告/混淆矩阵 |
| A2–A4 | 各自 `experiment_config.json`、`train_log.csv`、曲线、测试集指标（一次性） |
| A5 | 难例 case 列表与结论 |
| B | 38 类 `class_names.json`、新数据划分统计、新类别测试子集报告、回归对比表 |

## 10. 待验证问题清单（不预设结论）

- ColorJitter / RandomErasing / Mixup 对细粒度品种分类的实际收益；
- 更大 backbone 在本硬件上的显存与耗时代价；
- 扩充数据后每类 150+ 张时 Macro-F1 的实际提升幅度；
- 混淆对中标注噪声的占比；
- 新增类别对旧类别的遗忘程度。
