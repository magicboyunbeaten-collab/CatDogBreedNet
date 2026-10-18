# 正式模型切换报告：V1 基线 → V1.1（A3b + patience=10）

> 切换日期：2026-10-18
> 候选模型：`artifacts/exp_esp_p10_seed42/best_model.pth`
> 新默认版本：`v1_1_37_optimized`
> 切换前 HEAD：`55f1d97`（早停对比实验提交）
>
> **本报告只记录"已发生的事"与"已测得的结果"。所有指标均为真实运行输出，
> 未重新训练模型、未修改原始数据、未清除演示数据库、未覆盖历史评估报告。**

---

## 1. 切换结论

**已成功将 V1.1（A3b 分层学习率 + patience=10，seed 42）设为正式默认模型。**

- 默认加载路径**保持不变**：`artifacts/best_model.pth`
  （`启动系统.bat`、`启动后端.bat`、`backend/app/config.py` 均依赖此路径，
  因此**未修改任何启动脚本**）
- 同时建立**版本化生产目录** `artifacts/v1_1_37_optimized/`，
  与训练实验目录 `artifacts/exp_esp_*` 明确分离
- V1 基线已完整备份至 `artifacts/backup_v1_20261018/`，**可随时回滚**

---

## 2. 切换前闸门核验（18 项全部通过）

| 闸门项 | 结果 |
|---|---|
| 候选权重文件存在 | PASS |
| 当前正式权重/类别映射存在 | PASS |
| 候选 `arch` | `resnet18` PASS |
| 候选 `num_classes` | 37 PASS |
| 候选 `class_names` 长度 | 37 PASS |
| `fc.weight` 形状 | `(37, 512)` PASS（ResNet50 会是 `(37, 2048)`） |
| `layer4.1.conv1.weight` | `(512,512,3,3)` PASS |
| ResNet18 特有层结构 | PASS |
| **候选类别顺序 vs 正式 `class_names.json`** | **逐项相同（顺序敏感比较）** PASS |
| 候选类别顺序 vs 候选目录 `class_names.json` | 相同 PASS |
| 类别集合无重复 | PASS |
| `load_checkpoint` 真实加载候选 | 成功，37 类 PASS |
| 加载后类别顺序一致 | PASS |
| 前向输出形状 | `(1, 37)` PASS |
| eval 预处理输出 | `(3, 224, 224)` PASS |
| 预处理确定性（同图两次相同） | PASS |
| `verify_class_mapping` 硬校验 | 通过（服务不会拒绝启动） PASS |
| Git 工作区状态 | 干净，HEAD `55f1d97` PASS |

> 闸门脚本：`.cache/verify_gates.py`（一次性工具，未入库）；
> 结果快照：`.cache/switch_gates.json`。

---

## 3. 文件哈希（切换凭据）

| 文件 | SHA256 |
|---|---|
| **候选权重**（现正式默认） | `89ef468f199c6d1550fec2638c5ea6f8ef7ad543e57f8ec82c4263c121b1a256` |
| **V1 权重**（已备份） | `3051ab73ea96743c3aebd6df5eb82d911d0dc59b3fb2acacca552fcd118bab48` |
| V1 `last_model.pth`（已备份） | `58e188a953e3b645...` |
| `class_names.json`（V1 与 V1.1 内容相同） | `24120035f4af1c4945ad6e6eb1d82fa1af8b1fd3a9e383ab0246c464dfce75e6` |
| V1 `experiment_config.json`（已备份） | `f680c66d7feeca46...` |
| V1.1 `experiment_config.json` | `3823098c4a8fc3fe...` |

`class_names.json` 两侧 SHA256 相同，印证闸门 3 的"类别映射逐项一致"结论。

---

## 4. 目录结构与实际加载路径

```
artifacts/
├── best_model.pth          # ← 默认加载路径（现为 V1.1，SHA 89ef468f…）
├── last_model.pth          # ← 与 best 同属 V1.1
├── class_names.json        # ← 内容与 V1 相同（37 类，顺序一致）
├── experiment_config.json  # ← 反映 A3b + epochs 30 + patience 10
├── model_version.json      # ← 新增：当前默认版本的指针（与版本目录内容相同）
├── backup_v1_20261018/     # ← V1 可恢复备份（不入 Git 的 .pth + manifest）
│   ├── best_model.pth
│   ├── last_model.pth
│   ├── class_names.json
│   ├── experiment_config.json
│   └── BACKUP_MANIFEST.json
└── v1_1_37_optimized/      # ← 权威版本化生产目录
    ├── best_model.pth
    ├── last_model.pth
    ├── class_names.json
    ├── experiment_config.json
    └── model_version.json
```

**实际加载链路**（启动日志实证）：

```
backend/app/config.py  Settings.weights_path = ARTIFACTS_DIR/"best_model.pth"
  → backend/app/services/predictor.py  PredictorService(weights_path, device)
    → ml/predictor.py  Predictor → ml/model.py  load_checkpoint()
      → ml/dataset.py  build_transforms(train=False)   # 与训练/评估同一条预处理
```

启动日志实测输出（`uvicorn` stderr）：

```
INFO:     database ready: app.db
INFO:     class mapping verified against class_names.json (37 classes)
INFO:     model ready: version=v1_1_37_optimized arch=resnet18 classes=37 device=cuda (weights: best_model.pth)
INFO:     Application startup complete.
```

版本 ID 与类别数已明确打印；**只打印权重文件名，不暴露完整服务器路径**
（`/api/health` 响应体也未添加版本字段，避免向普通用户暴露内部信息）。

---

## 5. 指标：三类口径分开列示

### 5.1 原始 V1 基线（阶段 2/3，**原始 `data/processed` 划分**）

| 指标 | 值 |
|---|---|
| test Top-1 Accuracy | 0.8035 |
| test Macro-F1 | 0.8022 |
| test Weighted-F1 | 0.8026 |
| val 最佳 Accuracy | 0.8401（epoch 8 / 10） |
| 训练策略 | ResNet18 全网络 lr=1e-3，patience=3，10 轮 |

来源：`reports/test_metrics.json`、`reports/train_log.csv`（阶段 3 报告未改动）。

### 5.2 A3b 多种子实验汇总（**`data/processed_clean` 清洁划分**，n=5）

| 指标 | 值 |
|---|---|
| test Accuracy | 0.8851 ± 0.0035 |
| test Macro-F1 | 0.8836 ± 0.0036 |
| test Weighted-F1 | 0.8844 ± 0.0035 |
| 单张延迟 | 2.2968 ± 0.0848 ms |

来源：`reports/earlystop_results/summary_test.json`（patience=10 组，5 种子）。
这是**整组的统计summary**，不是单一模型的保证值。

### 5.3 正式部署的 seed42 单模型（**`data/processed_clean` 清洁划分**）

| 指标 | 值 |
|---|---|
| **验证集 Accuracy** | **0.9158** |
| **验证集 Macro-F1** | **0.9151** |
| **测试集 Accuracy** | **0.8885** |
| **测试集 Macro-F1** | **0.8875** |
| **测试集 Weighted-F1** | **0.8883** |
| **单张延迟（batch=1，CUDA 同步）** | **2.354 ms** |
| 最佳 epoch / 实际轮数 | epoch 9 / 19 轮（上限 30，patience=10） |

来源：`reports/exp_esp_p10_seed42/test_eval/test_metrics.json`、
`reports/earlystop_results/p10_seed42.json`。

> **口径声明（重要）**：以上 seed42 指标是**该 seed42 模型在
> `data/processed_clean` 清洁划分上的已报告结果**，
> **并非所有运行环境下的性能保证**。实际表现会随输入图片分布、
> 硬件、批大小、推理框架版本而变化。
>
> **协议差异提示**：5.1 使用原始 `data/processed` 划分，5.2/5.3 使用
> `data/processed_clean` 去重划分（train 3288 / val 368 / test 3669），
> 训练数据与选模过程已不同，**三者不是同条件直接比较**。

---

## 6. 真实冒烟测试结果

测试图片：从 `data/processed_clean/test/` 按品种选取 8 张真实图片，
覆盖猫（Abyssinian、Ragdoll）、狗（beagle、两种斗牛犬、keeshond、
samoyed、chihuahua），其中包含诊断中已知最弱与最强品种。

### 6.1 CLI（`python -m ml.predict`，默认路径）

| 品种（文件夹标签） | Top-1 预测 | 分数 | 是否正确 |
|---|---|---|---|
| Abyssinian | Abyssinian | 0.9954 | OK |
| Ragdoll | Ragdoll | 0.9926 | OK |
| beagle | beagle | 0.9889 | OK |
| american_pit_bull_terrier | staffordshire_bull_terrier | 0.9937 | MISS（已知最弱混淆对） |
| staffordshire_bull_terrier | staffordshire_bull_terrier | 0.9916 | OK |
| keeshond | keeshond | 0.8464 | OK |
| samoyed | samoyed | 0.9992 | OK |
| chihuahua | chihuahua | 0.8741 | OK |

**8/8 推理成功，7/8 Top-1 正确。** 唯一 MISS 是
`american_pit_bull_terrier → staffordshire_bull_terrier`，正是 U1/A5 诊断中
记录的最弱混淆对（两者 Macro-F1 分别 0.58 / 0.62），属预期行为而非缺陷。

### 6.2 HTTP API（`/api/predict`）

| 项目 | 结果 |
|---|---|
| 推理成功 | **8/8** |
| Top-1 正确 | **7/8**（同上） |
| **Top-3 品种序列与 CLI 逐位一致** | **8/8**（连置信度都完全相同） |
| 新入库记录 | ID 82–89 |

### 6.3 真实浏览器（Chrome，`/predict` → `/history` → `/stats`）

| 项目 | 结果 |
|---|---|
| 页面渲染 | 正常（标题"猫狗品种分类识别系统"、上传控件、"模型已就绪"） |
| 上传 samoyed_1.jpg 并识别 | **记录 #90，Top-1 萨摩耶犬 99.9%** |
| Top-2 / Top-3 | 大白熊犬 0.03% / 荷兰毛狮犬 0.03% |
| 推理耗时 | 3.5 ms（预处理 2.1 ms，服务端总 153.3 ms） |
| 中文品种名 | 正确（萨摩耶犬/大白熊犬/荷兰毛狮犬） |
| 历史页 | 10 行记录，#90 显示 samoyed 99.92% |
| 统计页 | 总识别次数 90、2 张图表正常渲染（Top 10 分布 + 每日趋势） |
| 数据库 | `integrity_check: ok`，记录 81 → **90**（API 8 + 浏览器 1），ID 连续 |

截图存证：`.cache/switch_screenshots/stats.png`、`history.png`。

**CLI、API、浏览器三端结果完全一致**，证明同一权重、同一预处理、
同一类别映射在所有入口生效。

---

## 7. 回归测试

| 项目 | 结果 |
|---|---|
| 后端 `pytest tests/` | **142/142 通过**（含新增 9 个 `PredictorService` 用例） |
| 前端 Vitest | **54/54 通过**（9 个测试文件） |
| `npm run build` | **成功**（1.85s；仅既有的 chunk >500kB 告警，与本次改动无关） |

---

## 8. 新增代码改动

| 文件 | 改动 |
|---|---|
| `backend/app/services/predictor.py` | 新增 `read_model_version()`；`PredictorService` 增加 `weights_path`/`model_version` 属性；启动日志改为打印 `version=<id> arch=resnet18 classes=<n> device=<dev> (weights: <文件名>)`，**不暴露完整服务器路径**；版本文件缺失或损坏时服务仍可启动（`version=unknown`） |
| `tests/test_predictor_service.py` | **新增 9 个用例**：版本文件读取（存在/缺失/损坏/非 dict）、启动日志含版本与类别数且不含完整路径、无版本文件时 `version=unknown`、类别映射不一致时拒绝启动（安全网） |

**过程中发现并修正的问题**：首次启动时日志显示 `version=unknown`——
原因是 `read_model_version` 在权重**同目录**查找，而版本文件起初只放在
`artifacts/v1_1_37_optimized/`。已在 `artifacts/` 下补放一份
`model_version.json`（内容与版本目录完全相同），重启后日志正确显示
`version=v1_1_37_optimized`。

---

## 9. 回滚方式

V1 基线完整备份在 `artifacts/backup_v1_20261018/`，含
`BACKUP_MANIFEST.json`（记录每个文件的 SHA256、字节数、来源与回滚命令）。

```powershell
Copy-Item 'artifacts\backup_v1_20261018\best_model.pth' 'artifacts\best_model.pth' -Force
Copy-Item 'artifacts\backup_v1_20261018\last_model.pth' 'artifacts\last_model.pth' -Force
Copy-Item 'artifacts\backup_v1_20261018\class_names.json' 'artifacts\class_names.json' -Force
Copy-Item 'artifacts\backup_v1_20261018\experiment_config.json' 'artifacts\experiment_config.json' -Force
```

回滚后重启后端即可。由于 V1 与 V1.1 的 `class_names.json` 内容完全相同
（SHA256 一致），回滚主要涉及权重文件。

> 备份**不依赖 Git**（模型权重本就不入 Git）；备份文件的哈希已在复制后
> 立即复算校验，并在安装前再次复验通过。

---

## 10. 遵守的约束

| 约束 | 遵守情况 |
|---|---|
| 不重新训练模型 | 只用 `copy` 候选权重，未调用 `ml.train` |
| 不修改原始数据 | `data/processed` 仍 3311/369/3669；`data/processed_clean` 仍 3288/368/3669 |
| 不清除演示数据库 | 仅新增 9 条真实识别记录（81→90），`integrity_check: ok` |
| 不覆盖历史评估报告 | 阶段 3 的 `test_metrics.json`、`classification_report.csv`、`confusion_matrix.*`、`evaluation_summary.md` 均未改动 |
| 不把数据集/权重/DB/上传/缓存加入 Git | 见第 11 节忽略规则核对 |
| 保留 V1 可回滚 | `artifacts/backup_v1_20261018/` + `BACKUP_MANIFEST.json` |
| A5 难例人工审查任务 | 仍保留，未修改任何标签 |

---

## 11. 复现与审计

```powershell
cd E:\CatDogBreedNet
# 核验默认权重确实是 V1.1
.venv\Scripts\python.exe -c "import torch,json; p=torch.load('artifacts/best_model.pth',map_location='cpu',weights_only=False); print(p['arch'], p['num_classes'], p['val_acc'])"
# 查看当前默认版本元数据
Get-Content artifacts\model_version.json
# 查看 V1 备份清单
Get-Content artifacts\backup_v1_20261018\BACKUP_MANIFEST.json
```
