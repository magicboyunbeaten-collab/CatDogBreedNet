# V2.1 相近犬种候选提示 — 集成验收报告

> **阶段**：U5 集成验收（只验收与修正必要的功能问题）
> **候选模型**：V2.1 `artifacts/v2_1_136classes_seed42/best_model.pth`（136 类）
> **正式模型**：V1.1 `artifacts/best_model.pth`（37 类），**未切换、未改动**
> **报告目录**：`reports/v2_1_candidate_ui_review/`（未覆盖 `implementation_report.md` 等既有文件）
> **生成时间**：2026-10-19

---

## 0. 总结论

**验收通过。** 后端 API 验收 66/66、前端验收 8/8、APBT 限制验证 5/5；回归测试后端 233 passed、前端 73 passed、前端构建成功。V1.1 与 V2.1 权重、类别映射、数据目录、SQLite、uploads 前后完全一致。

过程中**发现并修正了 1 个必要的功能问题**：候选组此前只看 Top-K（默认 3），导致排名在 Top-3 之外的候选被当作 0 分，组内得分会显示"0%"从而歪曲模型输出；同时这也会低估组内总质量、使触发判定与阈值验证口径不一致（实测触发数 4 vs 预期 5）。已通过透传完整 softmax 向量修正，修正后触发数与阈值验证一致。

---

## 1. 验收环境（隔离）

| 项目 | 实现 |
|---|---|
| 模型加载 | 真实 `PredictorService`，`weights_path = artifacts/v2_1_136classes_seed42/best_model.pth` |
| 类别校验 | `class_names_path = artifacts/v2_1_136classes_seed42/class_names.json`（与 136 类权重匹配） |
| 数据库 | 临时目录 `app.db`（`tempfile.TemporaryDirectory`），与 `data/app.db` **物理隔离** |
| 上传目录 | 临时目录 `uploads/`，与项目 `uploads/` **物理隔离** |
| 请求方式 | `fastapi.testclient.TestClient` + `with` 上下文（驱动 lifespan），上传**原始图片字节**（不重新编码） |
| 正式配置 | `backend/app/config.py` 的 `weights_path` 默认值与 `candidate_group_enabled=False` **全程未改**；未在环境中设置 `CATDOG_WEIGHTS_PATH` |

验收脚本：`scripts/accept_candidate_group_api.py`、`scripts/export_candidate_triggers_val.py`、`scripts/verify_apbt_candidate_limit.py`、`frontend/tests/predictionResultAcceptance.test.js`。

---

## 2. 发现并修正的功能问题

### 2.1 问题：候选组被 Top-K 截断，组外候选被当作 0 分

**现象**：导出的触发清单中，`kelpie/n02105412_133.jpg` 的 `prob_american_bulldog = 0.00144`，但 `group_score_american_bulldog = 0.0`；该候选的真实排名是第 4，不在 Top-3 内。

**影响范围**：validation split 上 top-1 落入候选组的 36 张图片中，**34 张**至少有一个候选排在 Top-3 之外。

**后果**：
1. UI 会把模型实际给了非零概率的候选显示为"0%"，歪曲模型输出；
2. 组内总质量被低估，触发判定比阈值验证时更严格——实测触发 **4 张**，而按阈值验证（用完整概率）应为 **5 张**，两者口径不一致。

**修正**（最小改动，共 4 个文件）：
- `ml/predict.py::predict_from_tensor` — 结果中新增内部字段 `probabilities`（完整 softmax 向量）；API 响应 schema 不暴露它；
- `ml/predictor.py::Predictor.predict_pil` — 透传该字段；
- `backend/app/services/candidate_group.py::build_candidate_group` — 新增可选参数 `probabilities`，提供时以其为准，未提供时退回原行为（向后兼容）；
- `scripts/export_candidate_triggers_val.py` — 传入完整概率向量，与 API 链路一致。

**修正后**：触发数 **4 → 5**，与 U5 阈值验证完全一致；新增 5 个单测（`tests/test_candidate_group.py`），后端测试 228 → 233。

> **未修改**：`CANDIDATE_GROUP` 成员、阈值（mass 0.30 / margin 0.40）、`THRESHOLD_VERSION`。

### 2.2 非问题：GPU 推理的跨批次非确定性

首次验收有 8 项"原始分数不一致"失败，差异量级 1e-4。经专项验证：

| 实验 | 结果 |
|---|---|
| 同一张图连续两次 batch=1 | **完全一致** |
| 同一张图 batch=1 vs batch=32 | 最大绝对差 **5.73e-4** |

结论：这是 GPU 推理在不同 batch size 下的正常非确定性（cudnn 算法差异），**不是功能缺陷**。导出清单用 batch=32，API 用 batch=1。验收判据已改为：跨批次比较用 1e-3 容差（并注明原因），同时增加**精确的内部一致性检查**作为"未篡改概率"的硬证据。

---

## 3. Validation split 触发样本清单

**仅使用 validation split（2,079 张），未读取 test split，未调整阈值。**

| 统计 | 数值 |
|---|---|
| val 图片总数 | 2,079 |
| top-1 落入候选组 | 36（1.73%） |
| top-1 为 APBT | 13（0.63%） |
| **实际触发候选组** | **5（0.24%）** |
| 触发样本中真标签确在组内 | 3/5（60%） |

完整清单：`val_candidate_triggers.csv`。

| # | 真实标签 | 图片 | Top-1 | Top-1 分 | AmStaff | SBT | AmBull | 组内得分（AmStaff/SBT/AmBull） |
|---|---|---|---|---|---|---|---|---|
| 1 | `american_pit_bull_terrier` | `american_pit_bull_terrier_11.jpg` | AmStaff | 0.5337 | 0.5337 | 0.4619 | 0.0008 | 53.60 / 46.39 / 0.08 |
| 2 | `american_staffordshire_terrier` | `n02093428_3269.jpg` | AmStaff | 0.3786 | 0.3786 | 0.0000 | 0.0008 | 100.00 / 0.00 / 0.21 |
| 3 | `kelpie` | `n02105412_133.jpg` | AmStaff | 0.3900 | 0.3900 | 0.0002 | 0.0014 | 99.58 / 0.05 / 0.37 |
| 4 | `rhodesian_ridgeback` | `n02087394_9698.jpg` | AmStaff | 0.5991 | 0.5991 | 0.0334 | 0.2529 | 67.66 / 3.77 / 28.57 |
| 5 | `staffordshire_bull_terrier` | `staffordshire_bull_terrier_160.jpg` | SBT | 0.4256 | 0.0290 | 0.4256 | 0.0004 | 6.80 / 93.09 / 0.10 |

**观察**：5 个触发样本中，只有 3 个的真实标签确在候选组内；另 2 个分别是 `kelpie` 与 `rhodesian_ridgeback`（模型把非斗牛犬误判为 AmStaff，且组内确实存在竞争）。这与任务设计一致——候选提示表达的是"模型在这几个品种间难以区分"，**不等于模型正确**。

**未触发原因分布**（2,074 张）：top-1 不在候选组内 2,043 张；组内分差 > 0.40（模型已有明确偏好）32 张；组内总质量 < 0.30 的 0 张。

---

## 4. 验收项明细

### 4.1 API 层（隔离环境，66/66 通过）

对 5 个触发样本 + 3 个未触发对照 + 5 个关闭开关复测，每项均通过 TestClient 走真实 `POST /api/predict`。

| # | 验收项 | 结果 |
|---|---|---|
| A1 | 触发样本 `candidate_group.triggered == true` | PASS（5/5） |
| A2 | 三项候选齐全且中文名正确 | PASS |
| A3 | 组内得分之和 ≈ 100 | PASS |
| A4 | 原始 Top-1 品种与导出清单一致 | PASS |
| A5 | 原始 Top-1 分数与清单一致（GPU 容差 1e-3） | PASS |
| A6 | 候选组 `top1_confidence` 与原始 Top-1 **完全一致**（精确） | PASS |
| A7 | 各候选 `original_confidence` 之和 = `group_mass`（精确） | PASS |
| A8 | 组内得分均等于各自原始概率归一化（精确） | PASS |
| B1 | 未触发对照：不触发且原始 Top-K 正常 | PASS（3/3） |
| C1 | 关闭开关后响应不含候选组 | PASS（5/5） |
| C2 | 关闭开关后 Top-1 与开启时一致 | PASS |
| D1 | 数据库表无任何候选组字段 | PASS |
| D2 | 数据库记录与响应一致 | PASS |

**数据库字段核对**（隔离临时库）：`['id', 'image_path', 'predicted_breed', 'confidence', 'top_k_json', 'inference_ms', 'created_at']` —— 与改动前完全一致，**候选组绝不入库**。

### 4.2 前端层（真实 API 响应，8/8 通过）

`frontend/tests/predictionResultAcceptance.test.js` 直接读取 `acceptance_api_responses.json`（隔离环境的真实响应），而非 mock 数据。

| # | 验收项 | 结果 |
|---|---|---|
| A | 每个触发响应都渲染三个候选品种 | PASS |
| B | 组内得分和 100 且标注"候选组内相对得分" + "不是整体置信度" | PASS |
| C | 组内得分严格等于各自原始概率归一化 | PASS |
| D | 原始 Top-K 与模型首选不被替换；`top1_breed`/`top1_confidence` 与 `predictions[0]` 一致 | PASS |
| E | 用户选择单独呈现，不覆盖模型预测（props 未被修改） | PASS |
| F | 未触发响应不渲染候选区 | PASS |
| G | 关闭开关响应不渲染候选区 | PASS |
| H | 解释提示含"登记品种""单张图片未必足以可靠区分" | PASS |

### 4.3 APBT 限制（5/5 通过）

`scripts/verify_apbt_candidate_limit.py`：

| # | 验收项 | 结果 |
|---|---|---|
| 1 | APBT **不在**候选组成员中 | PASS — `CANDIDATE_GROUP=[amstaff, SBT, american_bulldog]` |
| 2 | top-1 为 APBT 时不触发候选组 | PASS — `triggered=False` |
| 3 | 不触发原因为 `top-1 不在候选组内` | PASS |
| 4 | APBT 高置信度（0.99）时同样不触发 | PASS |
| 5 | val 中 top-1 为 APBT 的 **13 张**图片全部不会触发 | PASS |

**未把 APBT 加入候选组。** 明细见 `apbt_top1_val_images.csv`。

---

## 5. 通过项汇总

1. V2.1 候选权重在隔离环境正常运行，正式模型默认路径未变；
2. 触发清单仅由 validation split 产出，未读 test split，未调阈值；
3. 候选区正确显示三个品种，中文名正确；
4. 组内得分归一化正确，和恰为 100，且严格来自原始概率；
5. 原始 Top-K 与模型首选不变，概率未被篡改（精确内部一致性证明）；
6. 用户选择仅在界面单独呈现，不覆盖模型预测，不写入数据库；
7. 关闭 `CATDOG_CANDIDATE_GROUP_ENABLED` 后行为复原；
8. 数据库历史记录未被覆盖（隔离库 + 项目库 SHA256/行数不变）；
9. APBT 作 Top-1 时不触发候选组，候选组成员未改；
10. 回归测试与构建全部通过；
11. 保护对象前后一致。

## 6. 失败项

**无遗留失败项。** 首次运行的 8 项"失败"经查证为 GPU 跨批次非确定性（见 2.2），已通过修正判据 + 增加精确内部一致性检查解决；由此暴露的 Top-K 截断问题（见 2.1）已修复并复验通过。

---

## 7. 仍需人工决定的问题

### 7.1 候选组触发率极低（0.24%）

根因是模型在这三个品种间通常很确定（子总体组内分差中位数 0.7625）。这意味着候选提示是**保守兜底**而非高频功能。

- 若要提高触发率，需放宽 `MARGIN_THRESHOLD`（当前 0.40）——但那会让"模型已有明确偏好"的样本也进入候选组，违背任务口径；
- **建议**：维持现状，在论文/演示中说明这是保守设计。若业务方认为提示太少，需单独评审放宽阈值并重新用 validation split 验证。

### 7.2 APBT 不在候选组内，最常见的误判场景不触发

V2.1 中 APBT↔AmStaff 是最大混淆来源（APBT 被预测为 AmStaff 21 例、反向 2 例），但按任务口径 APBT 保持独立类别，**不在**候选组内。因此当用户上传 AmStaff 而模型判成 APBT 时，候选组不会展示。

- 这是任务口径的直接结果，本轮**未**修改；
- 若未来要覆盖该场景，需要单独评审是否把 APBT 也纳入候选组（涉及类别口径变更，超出本次授权）。

### 7.3 前端无独立环境开关

前端按"后端是否返回 `candidate_group`"自适应渲染，没有独立的环境变量开关。后端开关默认关闭，因此默认行为与 V1.1 一致。

- 若需要在后端开启时也能按环境屏蔽前端渲染，需另行评审。

### 7.4 触发样本的"误触发"性质

5 个触发样本中有 2 个（`kelpie`、`rhodesian_ridgeback`）真实标签并非斗牛类——模型把其他犬种误判为 AmStaff 且组内确有竞争。候选提示如实反映了"模型不确定"，但用户可能误以为"候选中必有一个是正确的"。

- **建议**：保持现有文案（已明确"不代表模型已确认犬只的登记品种"），必要时可进一步加强提示。

---

## 8. 保护核对

| 检查项 | 结果 |
|---|---|
| V1.1 `artifacts/best_model.pth` SHA256 | `89ef468f…a256` **一致** |
| V2.1 候选权重 / `class_names.json` / `model_version.json` / `experiment_config.json` | SHA256 **一致** |
| `artifacts/backup_v1_20261018/`、`artifacts/v1_1_37_optimized/` | **一致** |
| `data/processed`、`processed_clean`、`raw`、`v2_processed`、`v2_processed_prev` | 文件数与字节 **一致** |
| SQLite（`data/app.db`） | 行数与 `integrity_check` **一致**（142 条 / ok） |
| `uploads/` | 142 个文件 **一致** |
| 正式模型默认路径 | `backend/app/config.py` 的 `weights_path` 默认值 **未改** |
| `class_names.json` 类别定义 | **未改** |
| 训练 | **未运行任何训练脚本** |

前后快照：`protection_snapshot_before.json` / `protection_snapshot_after.json`（自动比对通过）。

---

## 9. 测试与构建（均为实际执行）

| 命令 | 结果 |
|---|---|
| `.venv\Scripts\python.exe -m pytest tests/ -q` | **233 passed**（U5 后 228，+5 个新增用例） |
| `cd frontend; npm test`（`vitest run`） | **73 passed / 11 files**（U5 后 65，+8 个验收用例） |
| `cd frontend; npm run build` | **构建成功**（1.37s；chunk >500 kB 警告为既有情况） |
| `scripts/export_candidate_triggers_val.py` | 运行成功，读 val 2,079 张，触发 5 张 |
| `scripts/accept_candidate_group_api.py` | 运行成功，66/66 通过 |
| `scripts/verify_apbt_candidate_limit.py` | 运行成功，5/5 通过 |

---

## 10. 输出文件

`reports/v2_1_candidate_ui_review/` 新增：

| 文件 | 内容 |
|---|---|
| `acceptance_report.md` | 本报告 |
| `val_candidate_triggers.csv` | validation split 实际触发候选组的 5 张图片清单 |
| `val_candidate_group_stats.json` | 触发统计与未触发原因分布 |
| `acceptance_api_responses.json` | 隔离环境真实 API 响应留证（含全部 66 项检查明细） |
| `apbt_top1_val_images.csv` | val 中 top-1 为 APBT 的 13 张图片（均不触发） |
| `apbt_candidate_limit.json` | APBT 限制验证结果 |
| `protection_snapshot_before.json` / `_after.json` | 保护快照 |

---

## 11. Git 状态（未提交、未清理）

本轮**未执行 `git commit`**，未清理工作区，未覆盖既有诊断报告。

本轮修改/新增：

```
 M ml/predict.py                        # 透传完整 softmax 向量（内部字段）
 M ml/predictor.py                      # 透传 probabilities
 M backend/app/services/candidate_group.py   # 新增可选 probabilities 参数
 M tests/test_candidate_group.py        # +5 个用例（228 -> 233）
?? scripts/export_candidate_triggers_val.py
?? scripts/accept_candidate_group_api.py
?? scripts/verify_apbt_candidate_limit.py
?? frontend/tests/predictionResultAcceptance.test.js
?? reports/v2_1_candidate_ui_review/acceptance_report.md
?? reports/v2_1_candidate_ui_review/val_candidate_triggers.csv
?? reports/v2_1_candidate_ui_review/val_candidate_group_stats.json
?? reports/v2_1_candidate_ui_review/acceptance_api_responses.json
?? reports/v2_1_candidate_ui_review/apbt_top1_val_images.csv
?? reports/v2_1_candidate_ui_review/apbt_candidate_limit.json
```

（其余 `M` / `??` 项均为本任务开始前既有改动，原样保留。）

---

**验收完成并停止。未训练 V2.2，未自动提交 Git，未清理工作区，未覆盖既有诊断报告。等待人工确认。**
