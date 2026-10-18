# 早停策略（patience）配对对比报告

> 生成日期：2026-10-18
> 实验对象：A3b 分层学习率配置（ResNet18，head lr=1e-3 / backbone lr=1e-4）
> 数据：`data/processed_clean/`（train 3288 / val 368 / test 3669，37 类，
>       由 `b751c11` 构建并校验：pHash 跨划分近重复 0、MD5 跨划分 0、
>       跨集合簇 0、类别映射与 `artifacts/class_names.json` 逐项一致）
> 运行脚本：`scripts/run_earlystop_validation.py`
>
> **本报告不替换任何正式模型。** `artifacts/best_model.pth`、
> `class_names.json`、`experiment_config.json` 均未改动（mtime 仍为
> 2026-10-13）。所有实验权重在 `artifacts/exp_esp_*`。
> 测试集只在阶段二对**预先选定**的配置各评估一次。

---

## 1. 实验协议

**唯一变量是 `--patience`**，其余逐项一致（由脚本 `SHARED_TRAIN_ARGS` 强制）：

```
--arch resnet18 --augment baseline --freeze-strategy none --batch-size 32
--lr-head 1e-3 --lr-backbone 1e-4        # A3b 分层学习率
--step-size 5 --gamma 0.1                # StepLR 不变
--epochs 30                              # 统一最大轮数上限
--data-dir data/processed_clean
```

- 种子：`42, 2024, 7, 123, 20261017`（三组完全相同，共 15 个运行）
- 选模：按既有规则（**每 epoch 的 val accuracy**）保存 best checkpoint
- **统一 max_epochs = 30 的理由**：`StepLR(step_size=5, gamma=0.1)` 使 LR 在
  epoch 20 后已降至 1e-7（head）/ 1e-8（backbone），模型实质冻结，
  val_acc 在此之前必然 plateau，故 best_epoch ≤ 20，patience=10 最多跑到
  best+10 ≤ 30——30 足以容纳 patience=10 的实际效果。
- **两阶段分离**（从流程上杜绝"据 test 选 patience"）：
  - 阶段一 `--stage train-val`：只训练 + 只做**验证集**评估，**不读取 test**；
  - 依据验证集选定 patience 并**先记录理由**（第 4 节）；
  - 阶段二 `--stage test --patience 10`：仅对被选定的配置做 test 评估。

---

## 2. 阶段一结果（**仅验证集**，n=5）

### 2.1 各组 mean ± std

| patience | val Accuracy | val Macro-F1 | val Weighted-F1 | train/val 差距 | 跨种子 std(val Acc) | 实际轮数 | 训练耗时 |
|---|---|---|---|---|---|---|---|
| 3 | 0.8924 ± 0.0063 | 0.8918 ± 0.0059 | 0.8918 ± 0.0062 | 0.1002 ± 0.0140 | 0.0063 | 6.0 ± 2.9 | 121 ± 56 s |
| 5 | 0.9054 ± 0.0101 | 0.9047 ± 0.0102 | 0.9049 ± 0.0103 | 0.0965 ± 0.0081 | 0.0101 | 14.4 ± 3.0 | 288 ± 59 s |
| **10** | **0.9092 ± 0.0056** | **0.9081 ± 0.0059** | 0.9083 ± 0.0060 | **0.0957 ± 0.0048** | **0.0056** | 21.0 ± 5.1 | 421 ± 104 s |

### 2.2 逐种子明细（验证集）

| patience | 种子 | 最佳 epoch | 实际轮数 | val Acc | val Macro-F1 | train/val 差距 | 训练耗时 |
|---|---|---|---|---|---|---|---|
| 3 | 42 | 1 | 4 | 0.8995 | 0.8981 | 0.0813 | 81 s |
| 3 | 2024 | 1 | 4 | 0.8859 | 0.8844 | 0.0925 | 82 s |
| 3 | 7 | 8 | 11 | 0.8967 | 0.8964 | 0.1183 | 217 s |
| 3 | 123 | 3 | 6 | 0.8940 | 0.8930 | 0.1032 | 125 s |
| 3 | 20261017 | 2 | 5 | 0.8859 | 0.8869 | 0.1056 | 102 s |
| 5 | 42 | 12 | 17 | **0.9212** | 0.9206 | 0.0854 | 333 s |
| 5 | 2024 | 6 | 11 | 0.9022 | 0.9000 | 0.0996 | 223 s |
| 5 | 7 | 13 | 18 | 0.8940 | 0.8941 | 0.1045 | 361 s |
| 5 | 123 | 9 | 14 | 0.9022 | 0.9005 | 0.1023 | 282 s |
| 5 | 20261017 | 7 | 12 | 0.9076 | 0.9083 | 0.0909 | 240 s |
| 10 | 42 | 9 | 19 | 0.9158 | 0.9151 | 0.0888 | 380 s |
| 10 | 2024 | 17 | 27 | 0.9103 | 0.9079 | 0.1014 | 545 s |
| 10 | 7 | 16 | 26 | 0.9130 | 0.9124 | 0.0942 | 519 s |
| 10 | 123 | 6 | 16 | 0.9022 | 0.9002 | 0.0984 | 319 s |
| 10 | 20261017 | 7 | 17 | 0.9049 | 0.9051 | 0.0957 | 343 s |

### 2.3 配对差值（同种子相减，基准 = 当前默认 patience=3）

| 对比 | val Accuracy | val Macro-F1 | val Weighted-F1 | 全为正 | train/val 差距 |
|---|---|---|---|---|---|
| patience=5 vs 3 | +0.0130 ± 0.0104 | +0.0129 ± 0.0104 | +0.0131 ± 0.0104 | **4/5**（seed7 −0.0027） | −0.0037 |
| **patience=10 vs 3** | **+0.0168 ± 0.0059** | **+0.0164 ± 0.0059** | +0.0165 ± 0.0062 | **5/5** | −0.0045 |

patience=10 的逐种子 val Acc 差值：seed7 +0.0163、seed42 +0.0163、
seed123 +0.0082、seed2024 +0.0245、seed20261017 +0.0190
（范围 [+0.0082, +0.0245]）。

---

## 3. 选定 patience = 10（**依据验证集，未参考任何 test 结果**）

理由（按重要性排序）：

1. **均值最高**：val Acc 0.9092、val Macro-F1 0.9081，三组中最好；
2. **跨种子最稳**：std 0.0056 / 0.0059，是 patience=5（0.0101）的一半、
   与 patience=3（0.0063）相当但均值明显更高——即"更好且同样可复现"；
3. **配对差值 5/5 全正**：+0.0168 ± 0.0059，最小差值 +0.0082；
   而 patience=5 只有 4/5（seed7 轻微回退 −0.0027），不满足"稳健提升"标准；
4. **过拟合最轻**：train/val 差距 0.0957 ± 0.0048 为三组最小
   （patience=3 为 0.1002 ± 0.0140），且 std 也更小；
5. **代价可接受**：训练 421s vs 121s（约 3.5 倍）、21 轮 vs 6 轮。
   对于一次性最终训练这是可接受成本，且推理延迟不变（见第 5 节）。

**为什么更长训练有效（机制解释）**：A3b 的 head 学习率 1e-3 会让 val_acc
在第 1–2 轮就冲到高点随后回落（patience=3 因此在第 4 轮就停）；而
StepLR 在 epoch 5/10/15 把 LR 降到 1e-4/1e-5/1e-6 后，模型仍有明显提升空间
——patience=5/10 的最佳 epoch 分别落在 6–13 和 6–17，正好跨过这些衰减点。
** patience=3 过早切断了 LR 衰减带来的收益**，这与上一轮
`seed_validation_report.md` 第 8 节的发现一致。

---

## 4. 阶段二结果（**仅对预先选定的 patience=10**，n=5）

test 集每个种子只评估一次，结果**未参与**任何 patience 选择。

### 4.1 汇总（mean ± std）

| 指标 | 值 |
|---|---|
| test Top-1 Accuracy | **0.8851 ± 0.0035** |
| test Macro-F1 | **0.8836 ± 0.0036** |
| test Weighted-F1 | 0.8844 ± 0.0035 |
| 单张延迟（batch=1，CUDA 同步） | 2.2968 ± 0.0848 ms |
| 批吞吐 | 约 1554 images/s |

### 4.2 逐种子

| 种子 | test Acc | test Macro-F1 | test Weighted-F1 | 延迟(ms) | 吞吐(img/s) |
|---|---|---|---|---|---|
| 7 | 0.8883 | 0.8867 | 0.8874 | 2.359 | 1536.1 |
| 42 | 0.8885 | 0.8875 | 0.8883 | 2.354 | 1567.9 |
| 123 | 0.8801 | 0.8786 | 0.8796 | 2.348 | 1419.7 |
| 2024 | 0.8844 | 0.8830 | 0.8836 | 2.164 | 1656.2 |
| 20261017 | 0.8842 | 0.8824 | 0.8832 | 2.260 | 1591.3 |

**种子间标准差仅 0.0035–0.0036**，是 A3b patience=3（上一轮，std 0.0182）的
**约 1/5**——patience=10 不仅提高均值，还大幅降低运行间波动。

### 4.3 逐类 test Macro-F1（5 种子均值）

最弱 8 类：

| 品种 | Macro-F1 |
|---|---|
| american_pit_bull_terrier | 0.5818 ± 0.0240 |
| staffordshire_bull_terrier | 0.6187 ± 0.0210 |
| Ragdoll | 0.7154 ± 0.0083 |
| Bengal | 0.7730 ± 0.0129 |
| american_bulldog | 0.7760 ± 0.0107 |
| Birman | 0.7888 ± 0.0127 |
| Maine_Coon | 0.8036 ± 0.0151 |
| chihuahua | 0.8394 ± 0.0034 |

最强 5 类：japanese_chin 0.9881、keeshond 0.9867、leonberger 0.9850、
pug 0.9737、newfoundland 0.9682。

37 类中 6 类低于 0.80，仍是两种斗牛犬与 Ragdoll 最弱——与 U1 诊断的
"错误集中于外形近缘品种"一致，属于**细粒度判别**问题而非训练策略问题。

---

## 5. 与历史基线的对照（**注意协议差异，非同条件直接比较**）

| 口径 | test Acc | test Macro-F1 | 说明 |
|---|---|---|---|
| 原始划分基线（阶段 3，单次） | 0.8035 | 0.8022 | `data/processed`，ResNet18 全网络 lr=1e-3，patience=3，10 轮 |
| 清洁划分 baseline 配置（5 种子） | 0.8077 ± 0.0013 | 0.8055 ± 0.0014 | `data/processed_clean`，同架构同 lr，patience=3 |
| 清洁划分 A3b patience=3（5 种子） | 0.8729 ± 0.0185 | 0.8715 ± 0.0182 | 上一轮，`--epochs 10` |
| **清洁划分 A3b patience=10（5 种子）** | **0.8851 ± 0.0035** | **0.8836 ± 0.0036** | **本轮，`--epochs 30`** |

**协议差异说明**：

- 第 1、2 行的差异来自**数据划分**（去重）与训练数据量，不是同条件比较；
- 第 3、4 行的差异来自 **patience 与 max_epochs**：patience=3 在多数种子
  第 4 轮即停（max_epochs 10 或 30 对其无影响），因此该对比主要反映
  patience 本身；但严格说 max_epochs 已变，属**近似可比**而非完全同条件；
- 相对第 2 行（同划分、同架构、仅差学习率策略与 patience）：
  **Macro-F1 +0.0781**（0.8055 → 0.8836）。

---

## 6. 结论与建议

### 6.1 已被数据支持的结论

1. **patience=10 是三组中最优的早停策略**：验证集均值最高
   （val Acc 0.9092 / Macro-F1 0.9081）、跨种子最稳（std 0.0056）、
   过拟合最轻（train/val gap 0.0957）、配对差值 5/5 全正。
2. **patience=5 不满足"稳健"标准**：均值居中但 std 最大（0.0101），
   且 seed7 相对 patience=3 轻微回退（−0.0027），未达 5/5 全正。
3. **patience=3（当前默认）确实过早**：它在多数种子第 4 轮就停止，
   错过了 StepLR 衰减后（epoch 10–17）的明显提升。
4. **A3b + patience=10 的测试表现稳健**：test Macro-F1 0.8836 ± 0.0036，
   种子间波动约为 A3b patience=3 的 1/5。
5. **无推理代价**：单张延迟 2.2968 ms 与基线（2.29 ms）持平，
   批吞吐约 1554 img/s。
6. **残余弱点不在训练策略**：两种斗牛犬（0.58 / 0.62）与 Ragdoll（0.72）
   仍是最弱，属细粒度相似品种问题，需补充数据或更强特征（非本轮范围）。

### 6.2 建议（**待用户确认，本轮不执行**）

| 优先级 | 建议 | 说明 |
|---|---|---|
| P0 | 采用 **A3b + patience=10** 作为下一版默认模型 | 验证集与测试集双向支持；延迟不变；方差最小 |
| P0 | 正式训练时固定 `--epochs 30 --patience 10` | 与本次验证协议一致，保证可复现 |
| P1 | 若追求更高精度，可再试 patience=15/20 | 本轮只验证了 3/5/10；LR 在 epoch 20 后已冻结，预期收益有限 |
| P2 | 对最弱品种补充数据 | 两种斗牛犬/Ragdoll 是主要瓶颈 |

**明确未做**：

- **未替换** `artifacts/best_model.pth` 与 `class_names.json`；
- **未据 test 调整**任何参数——test 只在 patience 选定后评估一次；
- **未做** patience=15/20、新品种、其他架构实验；
- A5 的 147 个难例仍保留为人工审查任务，未修改任何标签。

---

## 7. 过程中发现并修复的代码缺陷

| 缺陷 | 影响 | 修复 |
|---|---|---|
| 实验运行器 `_run()` 打印子进程输出尾部时抛 `UnicodeEncodeError` | 子进程输出经 `errors="replace"` 解码含 U+FFFD，GBK 控制台无法编码，**整个运行器崩溃**（真实发生：val 评估已成功产出全部文件，运行器却死在打印 tail 上，导致 15 个运行全部中断） | 新增 `_console_print()` 按控制台编码安全转码；三个脚本统一修复 |
| `ml/evaluate.py` 的 `build_summary_markdown()` 在 `--no-benchmark` 时崩溃 | 传入空 dict 却直接取 `batch_bench['scope']`，报 `KeyError`。该路径历史从未执行（此前评估都带 benchmark），直到用 `--no-benchmark` 做验证集评估才触发 | benchmark 缺失时跳过计时章节并明确说明；硬编码的 "37 个类别" 改为 `metrics['num_classes']` |
| `run_earlystop_validation.py` 的 `summary["patiences"]` 被列表覆盖 | 汇总统计字典被替换成 `[3,5,10]`，mean/std 全部丢失（与 `run_seed_validation.py` 曾出现的同一类错误） | 键名改为 `patience_values` |
| `run_seed_validation.py` 的 `summary["configs"]` 被列表覆盖 | 同上，多种子汇总统计不可读 | 键名改为 `config_names` |

新增回归测试 2 个（`--split` 相关 8 个 + `--no-benchmark` 汇总 1 个 +
早停脚本无独立测试但被阶段一/二端到端验证）。
回归：`pytest tests/` **133/133**。

---

## 8. 产物与复现方式

```powershell
cd E:\CatDogBreedNet
$env:TORCH_HOME="E:\CatDogBreedNet\.cache\torch"

# 查看矩阵
.venv\Scripts\python.exe scripts\run_earlystop_validation.py --list

# 阶段一：训练 + 验证集评估（15 个运行，支持断点续跑）
.venv\Scripts\python.exe scripts\run_earlystop_validation.py --stage train-val

# 阶段二：仅对预先选定的 patience 做 test 评估（必须显式指定）
.venv\Scripts\python.exe scripts\run_earlystop_validation.py --stage test --patience 10
```

| 产物 | 路径 |
|---|---|
| 逐运行结果 | `reports/earlystop_results/p<P>_seed<S>.json` |
| 阶段一汇总 | `reports/earlystop_results/summary_train-val.json` |
| 阶段二汇总 | `reports/earlystop_results/summary_test.json` |
| 训练日志 | `reports/exp_esp_p<P>_seed<S>/train_log.csv` |
| 训练配置 | `artifacts/exp_esp_p<P>_seed<S>/experiment_config.json` |
| 验证集评估 | `reports/exp_esp_p<P>_seed<S>/val_eval/` |
| 测试集评估 | `reports/exp_esp_p<P>_seed<S>/test_eval/` |
| 实验权重 | `artifacts/exp_esp_p<P>_seed<S>/best_model.pth`（不入 Git） |

**Git 提交**：`0607357`（代码准备）、`7e5a268`（缺陷修复）、
本轮阶段一/二与报告（见文末提交号）。
