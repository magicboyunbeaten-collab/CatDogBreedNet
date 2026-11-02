# U5.2 四类相近犬种候选组 — 隔离环境验收报告

> **阶段**：U5.2 隔离环境 API/UI 验收
> **候选模型**：V2.1 `artifacts/v2_1_136classes_seed42/best_model.pth`（136 类）
> **正式模型**：V1.1 `artifacts/best_model.pth`（37 类），**未切换**
> **报告目录**：`reports/v2_1_four_breed_candidate_implementation/`
> **生成时间**：2026-10-19
> **测试集访问记录**：**0**（全部样本来自 validation split 与 U5.1 代表性清单）

---

## 0. 总结论

**隔离环境 API 验收 160/160 全部通过，前端真实响应验收 8/8 全部通过。**
四类候选组在真实链路上行为正确：四项候选齐全、组内得分归一化正确、
原始 Top-K 与模型首选不变、用户选择仅界面呈现、关闭开关后行为复原、
数据库 schema 与写入字段不变。

**与 U5.1 的一致性**：代表性样本的 Top-1 品种与 U5.1 清单**逐张一致**，
Top-1 分数差异在 GPU 跨批次非确定性范围内（实测 ≤ 3e-4，见 2.2）。

---

## 1. 验收环境（隔离）

| 项目 | 实现 |
|---|---|
| 模型加载 | 真实 `PredictorService`，`weights_path` 指向 V2.1 候选权重 |
| 类别校验 | `class_names_path = artifacts/v2_1_136classes_seed42/class_names.json` |
| 数据库 | 临时目录 `app.db`，与 `data/app.db` **物理隔离** |
| 上传目录 | 临时目录 `uploads/`，与项目 `uploads/` **物理隔离** |
| 请求方式 | `fastapi.testclient.TestClient` + `with` 上下文，上传**原始图片字节** |
| 正式配置 | `weights_path` 默认值与 `candidate_group_enabled=False` **全程未改** |

验收脚本：`scripts/accept_four_breed_candidate_api.py`。

---

## 2. 样本来源（全部来自 validation）

| 来源 | 数量 | 说明 |
|---|---|---|
| U5.1 `newly_triggered_by_apbt.csv` | **7** | 三类不触发但四类触发的代表性样本（本任务验收重点） |
| U5.1 `triggered_by_both_strategies.csv` | **5** | 两类策略都触发 |
| U5.1 `out_of_group_trigger_examples.csv` | **4** | 组外误触发样本 |
| 未触发对照（val 中非候选类） | **3** | Abyssinian ×3 |
| **合计** | **19** | 全部位于 `data/v2_processed/val` |

逐图明细：`validation_samples_four_breed.csv`（16 行代表性样本）。

### 2.1 代表性样本实测结果

| 真实标签 | Top-1 | p(Top-1) | 组内 mass₄ | 组内 margin₄ | 四类触发 |
|---|---|---|---|---|---|
| `american_pit_bull_terrier` | **APBT** | 0.4672 | 0.8581 | 0.0763 | 是 |
| `american_staffordshire_terrier` | **APBT** | 0.6081 | 0.9931 | 0.3531 | 是 |
| `american_staffordshire_terrier` | **APBT** | 0.6195 | 0.9995 | 0.2394 | 是 |
| `american_staffordshire_terrier` | AmStaff | 0.4656 | 0.5686 | 0.3640 | 是 |
| `american_staffordshire_terrier` | AmStaff | 0.5290 | 0.9943 | 0.0639 | 是 |
| `bull_mastiff` | **APBT** | 0.4709 | 0.7547 | 0.1903 | 是（组外误触发） |
| `bull_mastiff` | AmStaff | 0.4569 | 0.5548 | 0.3599 | 是（组外误触发） |
| `american_pit_bull_terrier` | AmStaff | 0.5337 | 0.9963 | 0.0718 | 是 |
| `american_staffordshire_terrier` | AmStaff | 0.3786 | 0.3794 | 0.3778 | 是 |
| `kelpie` | AmStaff | 0.3900 | 0.3916 | 0.3885 | 是（组外误触发） |
| `rhodesian_ridgeback` | AmStaff | 0.5991 | 0.8854 | 0.3461 | 是（组外误触发） |
| `staffordshire_bull_terrier` | SBT | 0.4256 | 0.4572 | 0.3945 | 是 |

### 2.2 与 U5.1 的一致性核对

| 核对项 | 结果 |
|---|---|
| Top-1 品种逐张一致 | **12/12 一致** |
| Top-1 分数 | 差异 ≤ 3.1e-4（GPU batch=1 vs batch=32 非确定性，U5 实测最大 5.73e-4） |
| `threshold_version` | 全部为 `val-2026-10-19-four-breed-b1`（U5.2 四类 B1） |
| 候选组成员 | 四项，含 APBT |
| 推理 batch / 预处理 / checkpoint | batch 32、eval transform、同一 V2.1 best checkpoint，与 U5.1 一致 |

**未为凑数调整任何阈值。**

---

## 3. API 验收明细（160/160 通过）

对 12 个触发样本 + 3 个未触发对照 + 12 个关闭开关复测 + 1 次 DB 核对，每项均通过 TestClient 走真实 `POST /api/predict`。

| # | 验收项 | 结果 |
|---|---|---|
| A1 | 代表性样本 `candidate_group.triggered == true` | PASS（16/16） |
| A2 | **四项候选齐全且中文名正确** | PASS |
| A3 | 组内得分之和 ≈ 100 | PASS |
| A4 | 组内得分均等于各自原始概率归一化（精确） | PASS |
| A5 | 候选 `top1_confidence` 与原始 `predictions[0]` **完全一致** | PASS |
| A6 | `threshold_version` 为 U5.2 四类 B1 | PASS |
| A7 | 原始 Top-1 品种与 U5.1 清单一致 | PASS |
| A8 | 原始 Top-1 分数与 U5.1 一致（GPU 容差 1e-3） | PASS |
| B1 | 未触发对照：不触发且原始 Top-K 正常 | PASS（3/3） |
| C1 | 关闭开关后响应不含候选组 | PASS（12/12） |
| C2 | 关闭开关后 Top-1 与开启时一致 | PASS |
| D1 | 数据库表无任何候选组字段 | PASS |
| D2 | 数据库记录与响应一致 | PASS |

**数据库字段核对**（隔离临时库）：
`['id', 'image_path', 'predicted_breed', 'confidence', 'top_k_json', 'inference_ms', 'created_at']`
—— 与改动前完全一致，**候选组绝不入库，用户选择不写库**。

---

## 4. 前端验收明细（8/8 通过）

`frontend/tests/predictionResultAcceptance.test.js` 直接读取本次隔离环境
的真实响应 `acceptance_api_responses.json`（非 mock）。

| # | 验收项 | 结果 |
|---|---|---|
| A | 每个触发响应都渲染**四个**候选品种及中文名 | PASS |
| B | 组内得分和 100 且标注"候选组内相对得分" + "不是整体置信度" | PASS |
| C | 组内得分严格等于各自原始概率归一化 | PASS |
| D | 原始 Top-K 与模型首选不被替换；`top1_breed`/`top1_confidence` 与 `predictions[0]` 一致 | PASS |
| E | 用户选择单独呈现，不覆盖模型预测（props 未被修改）；`radios.length === 4` | PASS |
| F | 未触发响应不渲染候选区 | PASS |
| G | 关闭开关响应不渲染候选区 | PASS |
| H | 解释提示含"登记品种""单张图片未必足以可靠区分"，且**不含**"其中必有一个 / 一定是" | PASS |

---

## 5. 测试与构建（实际执行）

| 命令 | 结果 |
|---|---|
| `.venv\Scripts\python.exe -m pytest tests/ -q` | **244 passed**（U5.1 后 233，+11） |
| `cd frontend; npm test` | **74 passed / 11 files**（U5.1 后 73，+1） |
| `cd frontend; npm run build` | **构建成功**（801 ms） |

---

## 6. 保护核对

| 检查项 | 结果 |
|---|---|
| V1.1 `best_model.pth` SHA256 | `89ef468f…a256` **一致** |
| V2.1 四个文件 | SHA256 **一致** |
| 五个数据目录 + V1 备份 | 文件数与总字节 **一致** |
| SQLite / uploads | 142 条 ok / 142 文件 |
| `weights_path` 默认值 | `artifacts/best_model.pth`，**未改** |
| 候选开关默认值 | `False`，**未改** |
| 训练 | **未运行任何训练脚本，未生成 V2.2 权重** |
| test split | **访问次数 0** |

前后快照：`protection_snapshot_before.json` / `protection_snapshot_after.json`
（自动比对通过）。

---

## 7. 已知限制（如实说明）

1. **触发率 ≠ 模型准确率**：U5.1 validation-only 评估四类 B1 触发 12/2,079
   （0.58%），组内真实标签覆盖 8/12，组外触发 4/12。分母小，**仅指示性**。
2. **部分触发样本真实标签在组外**：本次验收的 16 个代表性样本中，
   `bull_mastiff` 2 张、`kelpie` 1 张、`rhodesian_ridgeback` 1 张属组外误触发。
3. **候选提示不解决真实品种可分性问题**：V2.1 在 APBT/AmStaff 上的 P/R/F1
   仍低（见 `reports/v2_1_diagnostics/`）。
4. **仍是低触发率功能**（约 0.58%），不是高频能力。
5. **`bull_mastiff` 的组外误触发**需人工判断可接受度。

---

## 8. 输出文件

| 文件 | 内容 |
|---|---|
| `acceptance_report.md` | 本报告 |
| `validation_samples_four_breed.csv` | 16 个代表性样本逐图明细（只用 val） |
| `acceptance_api_responses.json` | 隔离环境真实响应留证（含 160 项检查明细） |

---

## 9. Git 状态（未提交、未清理）

本轮**未执行 `git commit`**，未自动 `git add`，未清理工作区，未覆盖既有报告。

---

**验收完成并停止，等待人工复核。未自动开启候选功能、未切换模型、未训练 V2.2。**
