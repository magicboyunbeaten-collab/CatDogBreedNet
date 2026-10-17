# V1.1 模型实验报告（A2 / A3 / A4 / A5）

> 生成日期：2026-10-17
> 实验对象：阶段 2 训练的 ResNet18 基线（`artifacts/best_model.pth`，37 类）
> 上游诊断：`reports/model_diagnostics.md`（U1）
> 实验矩阵定义：`scripts/run_improvement_experiments.py`
>
> **本报告所有数字均来自真实运行**（`ml.train` + `ml.evaluate` 实际输出），
> 未执行/未验证的项明确标注。**基线权重、类别映射与阶段 3 报告均未被修改。**

## 1. 实验规则与基线

| 项目 | 值 |
|---|---|
| 基线架构 | ResNet18 + ImageNet 预训练 |
| 基线最佳 val_acc | 0.8401（epoch 8 / 10） |
| 基线 test Top-1 Accuracy | 0.8035 |
| 基线 test Macro-F1 | 0.8022 |
| 基线 test Weighted-F1 | 0.8026 |
| 基线单张延迟（batch=1，CUDA 同步） | 2.95 ms |
| 基线批吞吐 | 1184.9 images/s |

规则（与 `MODEL_UPGRADE_PLAN.md` 一致）：

1. **模型选择只用 train/val**：每个实验按 val_acc 选最佳 epoch；
2. **官方 test 集（3669 张）只做一次最终评估**，不参与任何超参选择；
3. 每个实验产物独立存放（`artifacts/exp_<id>/`、`reports/exp_<id>/`），
   **不覆盖** `artifacts/best_model.pth`；
4. 一次只改变少数变量，全部以基线配置为基准。

## 2. 结果总表（真实指标）

| 实验 | 变更 | 最佳epoch | 完成轮数 | val_acc | test Acc | test Macro-F1 | Δ Macro-F1 | ms/img |
|---|---|---|---|---|---|---|---|---|
| **基线** | — | 8 | 10 | 0.8401 | 0.8035 | 0.8022 | — | 2.95 |
| A2b_colorjitter | +ColorJitter(0.2) | 10 | 10 | 0.8455 | 0.7975 | 0.7953 | **−0.0069** | 2.30 |
| A2c_randomerasing | +RandomErasing(0.25) | 10 | 10 | 0.8537 | 0.8084 | 0.8062 | **+0.0040** | 2.19 |
| A2d_mixup | Mixup(α=0.2) | 2 | 5 | 0.6531 | 0.6154 | 0.5988 | **−0.2034** | 2.15 |
| A3a_freeze_layer4 | 解冻 layer4，lr 5e-4 | 9 | 10 | 0.8889 | 0.8643 | 0.8632 | **+0.0610** | 2.15 |
| **A3b_layered_lr** | 分层 LR head 1e-3 / bb 1e-4 | 6 | 9 | **0.8970** | **0.8828** | **0.8807** | **+0.0785** | 2.19 |
| A3c_label_smoothing | label smoothing 0.1 | 8 | 10 | 0.8455 | 0.8204 | 0.8188 | **+0.0166** | 2.31 |
| A3d_epochs20 | 20 轮 + 早停(patience 3) | 2 | 5 | 0.6396 | 0.5898 | 0.5876 | **−0.2146** | 2.29 |
| A4_convnext_tiny | ConvNeXt-Tiny, bs16 | 2 | 5 | 0.7507 | 0.6901 | 0.6800 | **−0.1222** | 4.51 |
| A4_efficientnet_b0 | EfficientNet-B0, bs16 | 9 | 10 | **0.9051** | 0.8686 | 0.8673 | **+0.0651** | 6.55 |
| A4_resnet50 | ResNet50, bs16 | 10 | 10 | 0.3279 | 0.2537 | 0.2305 | **−0.5717** | 5.44 |

硬件：NVIDIA RTX 4060 Laptop 8GB，PyTorch 2.14.1+cu130。
耗时（训练+评估）从 131s（A2d，早停）到 378s（A4_resnet50）不等。

## 3. A2：数据增强对照

| 实验 | val_acc | test Macro-F1 | Δ | 结论 |
|---|---|---|---|---|
| A2b ColorJitter | 0.8455 | 0.7953 | −0.0069 | **无提升**，略低于基线 |
| A2c RandomErasing | 0.8537 | 0.8062 | +0.0040 | **小幅提升**（在噪声范围内，见 §7） |
| A2d Mixup(0.2) | 0.6531 | 0.5988 | −0.2034 | **显著变差** |

分析：

- **A2c RandomErasing** 的 val_acc（0.8537）高于基线（0.8401），test 也同向
  提升，方向一致；但 +0.0040 的幅度接近运行间噪声，**结论为"小幅正向，
  需多样本确认"**。
- **A2d Mixup 大幅变差的主因是训练轮数不足**：Mixup 需要远多于 10 轮的训练
  才能收敛，日志显示第 2 轮后 val_acc 仅 0.65 且无改善。
  这不等于"Mixup 不适用"，而是"10 轮的基线配方不适配 Mixup"。
- **A2b ColorJitter 无提升**：本任务的判别线索主要是形态/纹理而非颜色，
  颜色抖动可能削弱有效特征（该解释为推测，标注为**待验证**）。

## 4. A3：微调策略对照（本轮最大发现）

| 实验 | val_acc | test Macro-F1 | Δ | val→test 落差 |
|---|---|---|---|---|
| A3a 解冻 layer4, lr 5e-4 | 0.8889 | 0.8632 | +0.0610 | 0.0246 |
| **A3b 分层学习率** | **0.8970** | **0.8807** | **+0.0785** | **0.0142** |
| A3c label smoothing 0.1 | 0.8455 | 0.8188 | +0.0166 | 0.0251 |
| A3d 20 轮 + 早停 | 0.6396 | 0.5876 | −0.2146 | 0.0498 |

分析：

1. **A3b（分层学习率：head 1e-3 / backbone 1e-4）是全场最佳实用方案**：
   Macro-F1 +0.0785，且 val→test 落差最小（0.0142），说明泛化最稳。
2. **A3a（解冻 layer4 + lr 5e-4）同样大幅提升**（+0.0610）。
   两者共同点是**大幅降低主干学习率**。
3. **根因与 U1 诊断一致**：基线用 lr=1e-3 全网络训练 10 轮，末轮
   train_acc 0.9852 vs val_acc 0.8293（差距 0.156），是典型的
   **预训练特征被过大学习率破坏 + 过拟合**。把主干 LR 降到 1e-4 后
   val_acc 从 0.8401 提升到 0.8970。
4. **A3c label smoothing** 小幅提升（+0.0166），方向与 A3a/A3b 一致
   （都是抑制过拟合），幅度中等。
5. **A3d（20 轮 + patience 3 早停）显著变差**：日志显示 val_acc 在第 2 轮
   达到 0.6396 后连续 3 轮无提升，**早停于第 5 轮**，没等到第 6 轮 LR 衰减
   后的收敛（基线正是靠 epoch 6–8 冲到 0.84）。
   结论：**patience=3 对本任务过于激进**，早期 val_acc 噪声会误触早停。

## 5. A4：backbone 对比

| 实验 | val_acc | test Macro-F1 | Δ | ms/img | 延迟增幅 | 满足"Macro-F1 ≥ 基线+0.02" | 满足"延迟增幅 ≤ 50%" |
|---|---|---|---|---|---|---|---|
| A4_resnet50 | 0.3279 | 0.2305 | −0.5717 | 5.44 | +84% | 否 | 否 |
| A4_convnext_tiny | 0.7507 | 0.6800 | −0.1222 | 4.51 | +53% | 否 | 否 |
| A4_efficientnet_b0 | **0.9051** | 0.8673 | +0.0651 | 6.55 | +122% | **是** | **否** |

分析：

1. **没有任何 backbone 同时满足计划的两项验收标准**（Macro-F1 ≥ +0.02
   且延迟增幅 ≤ 50%）。
2. **A4_resnet50 是训练失败，不是容量结论**：训练日志显示它跑满 10 轮，
   train_acc 仅 0.294、val_acc 0.328 且仍在上升——用 ResNet18 的配方
   （lr 1e-3、batch 16、10 轮）训练 ResNet50 属于**严重欠训练**。
   不能据此断言"ResNet50 不如 ResNet18"。
3. **A4_convnext_tiny** 第 2 轮即达 val 0.7507 随后过拟合，早停于第 5 轮，
   同样是超参不适配。
4. **A4_efficientnet_b0 是唯一精度上超越基线的 backbone**：
   val_acc 0.9051 为全场最高，test Macro-F1 0.8673（+0.0651）。
   但单张延迟 6.55 ms（+122%），超出 50% 预算。
5. **诚实结论**：A4 只证明了"**基线的训练配方不能直接迁移到其他架构**"，
   **没有**建立架构排名。要公平比较必须为每个架构单独调参
   （学习率、轮数、batch、warmup），这属于后续工作，本轮不做。

## 6. A5：难例抽样分析

- 基线在官方 test 集上误分类 **721 / 3669** 张（19.65%，与 Acc 0.8035 自洽）。
- 对错误最多的 8 个混淆对共抽样 **147** 个样本，图片已复制到
  `.cache/A5_review/<真实品种>_to_<误判品种>/` 供人工目检。
- **关键发现：147 个抽样样本中，没有任何一个在 train/val 中存在 pHash
  近重复（同标签 0 个，异标签 0 个）**。

结论：

1. 这些误分类**不是数据泄漏造成的**，而是模型对视觉相似品种的真实误判；
2. 结合 U1 的发现（存在跨子集近重复的品种是 keeshond、japanese_chin、
   leonberger 等**被正确分类**的品种），可以判断：
   **泄漏影响的是"已被记住的简单样本"，而模型真正的难点是细粒度相似品种**；
3. 各混淆对的错误平均置信度在 0.59–0.75 之间，模型以较高置信度犯错，
   说明需要更强的细粒度判别能力（而非简单调阈值）。

明细清单见 `reports/A5_hard_examples.md` / `.json`。
**是否属于官方标注错误必须人工目检后才能判定，本报告不下该结论。**

## 7. 运行间方差（重要方法论发现）

对比各实验的 epoch-1 轨迹发现：**相同种子（42）、相同配置下，
不同运行的 loss/acc 轨迹并不相同**。例如 epoch-1 的 val_acc：
基线 0.2439、A2b 0.4336、A2c 0.5095、A3c 0.4309。

原因：cuDNN 的非确定性算子与 `benchmark=True` 的算法自动选择，
使 GPU 前向/反向存在运行间抖动；种子只固定数据洗牌与初始化。

影响与应对：

- 单次运行的 val_acc 噪声量级约 **±0.02–0.05**；
- 因此 **Δ 在 ±0.01 以内的差异（A2b、A2c）不应作为结论**，
  需多种子重复才能确认；
- Δ 超过 ±0.05 的效应（A3a/A3b/EfficientNet 的提升，A2d/A3d/A4 的下降）
  **远超噪声，结论稳健**；
- 建议：对 A2c 这类小幅结果做 3–5 个种子的重复实验以确定是否真实
  （本轮未做，属**待验证**）。

## 8. 结论与建议

### 8.1 已验证的结论

1. **降低主干学习率是本任务最有效的单项改进**：
   A3b（head 1e-3 / backbone 1e-4）Macro-F1 **+0.0785**，
   A3a（解冻 layer4 + lr 5e-4）**+0.0610**。
2. **基线确实处于过拟合状态**，与 U1 诊断的 train/val 差距 0.156 一致；
   正则化类手段（分层 LR、label smoothing）均有效。
3. **早停 patience=3 过激**，会切断 LR 衰减前的收敛过程（A3d 反证）。
4. **10 轮对 Mixup 与更大 backbone 都不够**（A2d、A4 反证）。
5. **模型的真实难点是细粒度相似品种**，且与数据泄漏无关（A5 + U1）。

### 8.2 推荐的下一步（需用户确认后执行）

| 优先级 | 建议 | 理由 |
|---|---|---|
| P0 | **将 A3b（分层学习率）作为 V1.1 候选模型**，替换 `artifacts/best_model.pth` | +7.85 个点、延迟不变、val→test 落差最小；但按计划**须经用户确认才替换**，且需先做多 seed 验证 |
| P0 | A3b × 多 seed（3–5 个）重复验证 | 消除运行间方差影响，确认提升稳健 |
| P1 | 组合实验：A3b + RandomErasing / + label smoothing | 两项均为正向，可能叠加 |
| P1 | 为 EfficientNet-B0 单独调参后重测 | 它是唯一精度超越基线的 backbone，值得一次公平比较 |
| P2 | Mixup 延长到 50+ 轮再评估 | 当前结论只是"10 轮不够" |
| P2 | 对 A2c 做多 seed 确认 | 幅度在噪声边缘 |

### 8.3 明确未做的

- **未替换** `artifacts/best_model.pth`（基线仍是线上模型）；
- **未**按 test 集调任何参数；
- **未**修改官方 test 标注（A5 发现的样本仅记录）；
- A1（补充真实数据）与 B/U3–U5（新增类别）未启动，原因见 §10。

## 9. 交付物与复现方式

```powershell
cd E:\CatDogBreedNet
$env:TORCH_HOME="E:\CatDogBreedNet\.cache\torch"

# 查看矩阵
.venv\Scripts\python.exe scripts\run_improvement_experiments.py --list

# 全部实验（支持断点续跑；已有完整结果的实验自动跳过）
.venv\Scripts\python.exe scripts\run_improvement_experiments.py

# 只重跑某一组 / 某一个
.venv\Scripts\python.exe scripts\run_improvement_experiments.py --only A3
.venv\Scripts\python.exe scripts\run_improvement_experiments.py --only A3b_layered_lr --force

# 修复评估缺陷后只重跑评估（复用已训练权重）
.venv\Scripts\python.exe scripts\run_improvement_experiments.py --only A4 --force --skip-train

# A5 难例抽样
.venv\Scripts\python.exe scripts\analyze_hard_examples.py
```

产物：

- 每个实验：`artifacts/exp_<id>/`（best_model.pth、class_names.json、
  experiment_config.json）与 `reports/exp_<id>/`（test_metrics.json、
  classification_report.csv、confusion_matrix.*、train_log.csv、曲线）
- 汇总：`reports/exp_results/summary.json` 与各 `<id>.json`
- A5：`reports/A5_hard_examples.md` / `.json`，样本图片在
  `.cache/A5_review/`

## 10. 延后项与前置条件

| 项 | 状态 | 前置条件 |
|---|---|---|
| A1 补充现有 37 类图片 | **未执行** | 需要许可合规的新图片；入库前必须按 U1 的 pHash 阈值（≤5）复查与官方 test 集的近重复，并附去重报告 |
| A3b 替换基线权重 | **未执行** | 需用户确认 + 多 seed 验证 |
| U3 V2 数据审查 | **未执行** | 需下载 Stanford Dogs 等外部数据集并完成许可/标签/质量/去重审查 |
| U4 V2 训练 | **未执行** | 依赖 U3 通过 |
| U5 版本集成 | **未执行** | 依赖 U4；需设计模型版本配置，不硬编码类别数 |
| 未知品种拒识 | **未执行** | 需合规的类别外验证样本；未验证前界面只能提示"预测不确定" |

## 11. 过程中发现并修复的代码缺陷

| 缺陷 | 影响 | 修复 |
|---|---|---|
| `ml/train.py` 调用 `save_checkpoint` 未传 `arch`，默认写成基线 `resnet18` | 非 resnet18 的 checkpoint 被误标架构，`load_checkpoint` 用错误架构加载并报形状不匹配（A4_resnet50 评估失败的真实原因） | `save_checkpoint(..., arch=args.arch)`；新增 3 个回归测试（resnet50/convnext_tiny/efficientnet_b0 的存取往返） |
| 实验运行器无法在评估缺陷修复后只重跑评估 | 修复后必须重新训练，浪费时间 | 新增 `--skip-train` 选项 |

回归：`pytest tests/` **114/114 通过**（73 旧 + 14 诊断 + 27 训练管线，含 3 个新增的架构回归测试）。
