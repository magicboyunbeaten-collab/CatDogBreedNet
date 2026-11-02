# V2.1 相近犬种候选提示与边牧复核整合 — 实施报告（U5）

> **阶段**：U5（只做展示与资料整理）
> **正式模型**：V1.1（37 类）`artifacts/best_model.pth`，**未切换、未改动**
> **候选模型**：V2.1（136 类）`artifacts/v2_1_136classes_seed42/`，**仍为独立候选**
> **新报告目录**：`reports/v2_1_candidate_ui_review/`（未覆盖 `reports/v2_1_diagnostics/` 或 `reports/v2_1_coat_pitbull_diagnostics/`）
> **生成时间**：2026-10-19

---

## 1. 本次做了什么

两件事，**均未训练、未改标签、未改图片、未切换模型、未提交 Git**：

1. 为 V2.1 增加"相近犬种候选组"（AmStaff / SBT / American Bulldog）的**展示能力**，由显式开关控制、默认关闭；
2. 把用户已填入的边牧/柯利人工复核备注汇总成独立中文报告。

---

## 2. 修改 / 新增的代码文件与原因

| 文件 | 类型 | 原因 |
|---|---|---|
| `backend/app/services/candidate_group.py` | **新增** | 候选组判断与组内相对得分的**独立纯函数模块**：不依赖模型、可单测；原始概率路径完全不动 |
| `backend/app/config.py` | 修改 | `Settings` 新增 `candidate_group_enabled: bool = False`（env `CATDOG_CANDIDATE_GROUP_ENABLED`）与 `_env_bool` 解析；**`weights_path` 默认值未动** |
| `backend/app/schemas.py` | 修改 | 新增 `CandidateBreedItem` / `CandidateGroupInfo`；`PredictResponse` 新增**可选**字段 `candidate_group: ... \| None = None` |
| `backend/app/services/predictor.py` | 修改 | `PredictorService.__init__` 新增 `candidate_group_enabled` 参数（默认 False）与 `candidate_group(result)` 方法 |
| `backend/app/main.py` | 修改 | lifespan 中把开关透传给 `PredictorService`。**这是该文件唯一改动**（与 git HEAD 差异仅 1 处） |
| `backend/app/routes/predict.py` | 修改 | 仅在开关开启时计算候选组；失败不影响主流程；**数据库写入字段完全不变** |
| `frontend/src/utils/breedNames.js` | 修改 | 新增 `CANDIDATE_BREED_NAMES_ZH`（含 AmStaff 中文名）与 `CANDIDATE_GROUP`；`BREED_MAPPING_SIZE` **仍为 37** |
| `frontend/src/components/PredictionResult.vue` | 修改 | 条件渲染候选区 + 用户选择交互 |
| `tests/test_candidate_group.py` | **新增** | 36 个后端用例 |
| `frontend/tests/predictionResult.test.js` | **新增** | 8 个前端用例 |
| `frontend/tests/breedNames.test.js` | 修改 | 补 3 个用例（映射仍为 37、AmStaff 中文名、候选组标签） |
| `scripts/validate_candidate_group_thresholds.py` | **新增** | 只用 validation split 定阈值 |
| `scripts/summarize_coat_review.py` | **新增** | 只读汇总人工复核备注 |

---

## 3. 候选组触发规则与验证集阈值

### 3.1 规则

候选组固定为三个 canonical label（不得增删）：

- `american_staffordshire_terrier` — 美国斯塔福郡梗（AmStaff）
- `staffordshire_bull_terrier` — 斯塔福郡斗牛梗（SBT）
- `american_bulldog` — 美国斗牛犬

**APBT (`american_pit_bull_terrier`) 不在候选组内**，仍是独立原始类别；其高混淆问题在本报告第 6 节明确保留说明。

触发需**三条同时满足**：

1. 模型原始 top-1 ∈ 候选组；
2. 组内总质量 `group_mass = Σ p_j ≥ 0.30`；
3. 组内歧义 `group_margin = 组内top1 − 组内top2 ≤ 0.40`。

组内相对得分：

```
group_score_i = p_i / Σ p_j × 100
```

### 3.2 阈值依据（**只用 validation split**）

数据来源：`scripts/validate_candidate_group_thresholds.py` 对 `data/v2_processed/val` 的 **2,079 张**跑一次前向推理。**test split 从未被读取。**

| 观察 | 数值 |
|---|---|
| val 图片总数 | 2,079 |
| top-1 落入候选组的图片 | **36**（1.73%） |
| 该子总体的组内总质量中位数 | 0.8654 |
| 该子总体的组内分差中位数 | **0.7625** |
| 采用阈值后的触发数 | **5**（子总体 13.89%，全体验证图 **0.24%**） |
| 触发样本中真标签确在组内的比例 | 40.00%（2/5） |

**选择依据**：

- 组内分差中位数 0.7625 说明：**当模型 top-1 落到这三个品种时，它通常是相当确定的**。因此本特征按设计就是"少数真正歧义时才触发"的兜底提示，而非高频提示。
- 分差阈值上限设为 **0.40**：原始概率差超过该值就不应再视为"难以区分"，否则会把模型已有明确偏好的样本硬塞进候选组。
- 在 `margin ≤ 0.40` 的设计约束下，质量门槛从 0.05 提到 **0.30 不损失任何触发样本**（均为 5 个），故取同等效果下**更严格**的门槛，降低误触发可能。
- 阈值网格完整扫描结果见 `candidate_threshold_validation.csv`（72 行）。

**已知限制（必须说明）**：由于模型在组内通常很确定，该候选提示在验证集上触发率仅 0.24%。这意味着它**不是**一个高频功能，而是一个保守的歧义兜底。若要提高触发率，需要放宽分差阈值——但那会让"模型已明确的样本"也进入候选组，违背任务口径，故未采纳。

另一个限制：APBT 是 V2.1 中 APBT/AmStaff 混淆的最大来源，但按任务要求 APBT 不纳入候选组。因此当用户上传 AmStaff 而模型判成 APBT 时，候选组**不会**展示。这是任务口径的直接结果，已在第 6 节记录为待决策项。

---

## 4. API 新增字段与兼容策略

```jsonc
// POST /api/predict —— 新增字段（可选，默认 null）
"candidate_group": {
  "triggered": true,
  "threshold_version": "val-2026-10-19-v1",
  "top1_breed": "american_staffordshire_terrier",
  "top1_confidence": 0.34,
  "candidates": [
    {"breed": "american_staffordshire_terrier", "breed_zh": "美国斯塔福郡梗",
     "original_confidence": 0.34, "group_score": 37.7778}
  ],
  "available_candidates": ["american_staffordshire_terrier", "..."],
  "group_mass": 0.9,
  "group_margin": 0.04,
  "reason": "top-1 在候选组内、组内总概率 0.9000 ≥ 0.30 且组内分差 0.0400 ≤ 0.40"
}
```

**兼容策略**：

- 字段为 `CandidateGroupInfo | None = None`，**默认 null**；关闭开关或未触发时响应字段集合与 V1.1 完全一致；
- `predictions`（原始 Top-K 与原始 softmax）、`elapsed_ms`、`inference_ms`、`preprocess_ms`、`top_k`、`num_classes`、`note` **全部未改**；
- 历史接口 `HistoryItem` **未加**该字段，历史记录语义不变；
- 数据库写入字段（`image_path` / `predicted_breed` / `confidence` / `top_k_json` / `inference_ms` / `created_at`）**完全未变**，候选组绝不入库；
- V1.1（37 类，缺 AmStaff）下 `build_candidate_group` 直接返回 `None`，**不抛错**，自然退回原行为；
- 路由层对候选组计算包了 try/except，任何异常都不会影响主预测流程。

**不伪造置信度**：`group_score` 在 API 文档与前端文案中都明确标注为"候选组内相对得分，不是整体识别置信度、真实概率或准确率"；同时保留 `original_confidence` 供调试追踪。

---

## 5. 用户选择与模型原始预测如何分别保存

- 用户选择存于 `PredictionResult.vue` 的组件本地 `ref`（`userChoice`），**不调用任何 API、不写入数据库、不修改 props**；
- UI 上"模型预测"Top-K 区块与"你选择的品种"区块**视觉分离**（后者带主色竖线 + 浅底色），并附文字"模型首选仍为 …，未被替换"；
- 候选区只在 `result.candidate_group.triggered === true` 时渲染；未触发时页面与改动前逐像素一致；
- 第一阶段不持久化人工选择；如需持久化，按任务要求另行提交评审。

---

## 6. 边牧人工审核记录读取情况、统计结果与限制

### 6.1 读取情况（实际读到了什么）

| 项目 | 数量 |
|---|---|
| `coat_color_review_queue.csv` 总行数 | **183** |
| `review_notes` 非空（用户已填写） | **170** |
| `review_status` 非空 | **0** |

**读到了**：170 条用户手写的中文自由文本备注（如"复核结果黑白""复核结果白黄""人工复核纠正为黑白色"）。
**没读到**：结构化的 `review_status` 字段（该列为空）。

因此本汇总是**对自由文本的归一化与计数**，不是结构化人工结论。原 CSV **未被修改、重写或重命名**。

### 6.2 统计结果（`coat_review_grouped.csv`）

| 类别 | 人工备注归一化颜色 | n | 模型判对 | 模型判错 | 准确率 |
|---|---|---|---|---|---|
| `collie` | 黑白色 | 24 | 14 | 10 | 0.5833 |
| `collie` | 白黄色系 | 34 | 34 | 0 | 1.0000 |
| `collie` | 三色及以上 | 16 | 16 | 0 | 1.0000 |
| `collie` | 陨石色 | 4 | 4 | 0 | 1.0000 |
| `collie` | 多犬/非目标犬 | 5 | 5 | 0 | 1.0000 |
| `border_collie` | 黑白色 | 61 | 56 | 5 | 0.9180 |
| `border_collie` | 陨石色 | 11 | 11 | 0 | 1.0000 |
| `border_collie` | 三色及以上 | 4 | 2 | 2 | 0.5000 |
| `border_collie` | 多犬/非目标犬 | 5 | 5 | 0 | 1.0000 |

另有 3 条备注明确写"人工复核纠正为黑白色"（`collie/n02106030_15577.jpg`、`border_collie/n02106166_1055.jpg`、`border_collie/n02106166_4412.jpg`）。

### 6.3 限制（阅读上表前必读）

1. **样本选择偏差**：入队条件是"模型误判"或"自动毛色待复核"，因此**预测正确且毛色 confident 的图片根本不在队列里**。上表的准确率相对全量数据集**系统性偏低**。
2. 颜色组之间的**横向比较**比绝对数值更有参考价值，但即便横向比较也未排除"能否被自动定色"与"是否误判"之间的关联，**只能作为方向性参考，不能当作因果证据**。
3. 多犬/非目标犬备注（如"两只dog 左边白黄黑与右边黄白灰"）说明部分图片并非单一目标犬只，已单独归类，不计入颜色分组。
4. 未读取到任何"这张图标签错误"的结构化人工结论；本报告**不**对任何图片的品种归属下结论，也未据此更改任何标签。
5. 作为对照，全量诊断（`reports/v2_1_coat_pitbull_diagnostics/`）在 297 张上得到：`collie` 黑白 6/11、白黄系与红白 28/28、`border_collie` 黑白 21/22。两组数字方向一致。

---

## 7. 测试命令与结果（均为实际执行）

| 命令 | 结果 |
|---|---|
| `.venv\Scripts\python.exe -m pytest tests/ -q` | **228 passed**（改动前 192，新增 36） |
| `cd frontend; npm test`（`vitest run`） | **65 passed / 10 files**（改动前 54，新增 8 + breedNames 补 3） |
| `cd frontend; npm run build`（`vite build`） | **构建成功**（1.91s；chunk >500 kB 警告为既有情况，源自 element-plus + echarts） |
| `scripts/validate_candidate_group_thresholds.py` | 运行成功，读 val 2,079 张 |
| `scripts/summarize_coat_review.py` | 运行成功，读 183 行 |

后端 36 个新用例覆盖任务要求的全部 8 项：触发、得分和 100%、不改原始概率、低质量/大分差不触发、top-1 在组外、V1.1 缺 AmStaff 不报错、用户选择不覆盖原始预测、既有测试不回归。
前端 8 个新用例覆盖：未触发不渲染、功能关闭不渲染、三候选展示、得分和 100% 且标注非置信度、模型预测不被替换、用户选择单独呈现、解释提示含"登记品种"。

---

## 8. 保护核对

| 检查项 | 结果 |
|---|---|
| V1.1 `artifacts/best_model.pth` SHA256 | `89ef468f…a256` **一致**（与任务单期望值相同） |
| V2.1 候选 checkpoint / class_names / config | SHA256 **一致** |
| `data/processed_clean` / `data/v2_processed` | 文件数与字节 **一致** |
| `data/v2_processed_prev` | **一致** |
| SQLite 行数与 `integrity_check` | **一致** |
| `uploads/` 文件数 | **一致** |
| 正式模型默认路径 | `backend/app/config.py` 的 `weights_path` 默认值 **未改**，仍为 `artifacts/best_model.pth` |
| 正式模型版本元数据 | `artifacts/model_version.json` **未改** |
| `class_names.json` 类别定义 | **未改** |
| 训练 | **未运行任何训练脚本** |

前后快照：`protection_snapshot_before.json` / `protection_snapshot_after.json`（自动比对通过）。

---

## 9. 已知限制与待决策项

1. **候选组触发率低**（验证集 0.24%）：根因是模型在这三个品种间通常很确定（组内分差中位数 0.7625）。这是保守设计的必然结果。
2. **APBT 不在候选组内**：按任务要求 APBT 保持独立。因此"模型把 AmStaff 判成 APBT"这一最常见误判场景不会触发候选提示。若未来要覆盖该场景，需要单独评审是否扩展候选组（本任务未做）。
3. **人工复核尚未结构化**：`review_status` 仍为空，汇总基于自由文本。
4. **前端开关未接环境变量**：前端目前按"后端返回的 `candidate_group` 是否存在"自适应渲染；后端开关默认关闭，因此默认行为与 V1.1 一致。若需前端独立开关，另行评审。

---

## 10. 手工验证步骤（前端交互）

后端开启开关并加载 V2.1 后：

```powershell
$env:CATDOG_CANDIDATE_GROUP_ENABLED = "true"
$env:CATDOG_WEIGHTS_PATH = "artifacts/v2_1_136classes_seed42/best_model.pth"
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8000
```

1. 上传一张斗牛类图片，若返回体含 `candidate_group.triggered = true`，识别结果页会出现"外观相近的候选品种"区块；
2. 确认三个候选都列出，分数标注为"候选组内相对得分"，并附"不是整体识别置信度"的说明；
3. 点击其中某个候选的单选题，"你选择的品种"会单独出现，而上方"模型预测"Top-K 与分数**不变**；
4. 上传一张猫或非斗牛类犬图片，候选区**不出现**，页面与改动前一致；
5. 关闭开关重启后端，响应体中不再有 `candidate_group` 字段，历史页与统计页正常。

---

## 11. 输出文件

`reports/v2_1_candidate_ui_review/`：

| 文件 | 内容 |
|---|---|
| `implementation_report.md` | 本报告 |
| `coat_review_summary.md` | 边牧人工复核汇总（含样本偏差说明） |
| `coat_review_grouped.csv` | 按类别 × 人工颜色的分组统计 |
| `candidate_threshold_validation.csv` | 72 行阈值网格扫描结果 |
| `candidate_threshold_summary.json` | 分布统计与最终阈值依据 |
| `protection_snapshot_before.json` / `_after.json` | 保护快照 |

---

## 12. Git 状态（未提交、未清理）

本轮**未执行 `git commit`**。本任务开始前的既有改动全部原样保留。新增/修改文件：

```
 M backend/app/config.py
 M backend/app/main.py
 M backend/app/routes/predict.py
 M backend/app/schemas.py
 M backend/app/services/predictor.py
 M frontend/src/components/PredictionResult.vue
 M frontend/src/utils/breedNames.js
 M frontend/tests/breedNames.test.js
?? backend/app/services/candidate_group.py
?? scripts/validate_candidate_group_thresholds.py
?? scripts/summarize_coat_review.py
?? tests/test_candidate_group.py
?? frontend/tests/predictionResult.test.js
?? reports/v2_1_candidate_ui_review/
```

---

**已完成并停止，等待人工复核。未自动启动下一轮训练或模型切换。**
