# U5.5 V2.1（136 类）接入集成报告

> **正式模型**：**V2.1（136 类）** —— `artifacts/v2_1_136classes_seed42/best_model.pth`
> **回退目标**：V1.1（37 类）—— `artifacts/best_model.pth`，**文件未做任何改动**
> **候选组**：四类 B1（APBT / AmStaff / SBT / American Bulldog），**默认开启**，阈值与版本号未变
> **报告目录**：`reports/u5_5_v2_1_integration/`
> **生成时间**：2026-10-19
> **本阶段未训练任何模型，未生成 V2.2 权重，未访问 test split**

---

## 0. 八项必答结论

| # | 问题 | 结论 |
|---|---|---|
| 1 | **V2.1 是否已成为日常启动入口实际加载的默认模型？** | **是**。`cmd /c 启动后端.bat` 启动后 `/api/health` 返回 `num_classes: 136`，后端日志 `model ready: version=v2_1_136classes_candidate ... classes=136`。**证据来自运行中的服务，不是配置文件宣称** |
| 2 | **136 类中文映射是否 100% 完整？** | **是**。136/136 有中文名，键唯一 136、中文名唯一 136、缺失 0、含非中文字符的 0。审计表 `breed_mapping_audit.csv` 共 136 行 |
| 3 | **四类候选是否默认启用、触发/关闭验证是否通过？** | **是**。默认 `candidate_group_enabled=True`；触发（APBT/AmStaff/SBT 三场景）与关闭（`CATDOG_CANDIDATE_GROUP_ENABLED=false`）均通过 API + 浏览器双验证 |
| 4 | **所有测试与构建的实际结果** | `pytest tests/ -q` → **250 passed**；`npm test` → **79 passed / 11 files**；`npm run build` → **成功（855 ms）** |
| 5 | **V1.1 / V2.1 / 数据目录 / SQLite / uploads 的保护结果** | **全部一致**。V1.1 `89ef468f…a256` 不变；V2.1 四文件 SHA256 不变；五个数据目录 + V1 备份文件数与字节不变；SQLite **142 条 / integrity ok**；`uploads` **142 文件** |
| 6 | **逐文件变更清单与哪些原本就存在** | 见第 7 节与 `diff_summary.md`。本轮改动 13 个文件 + 新增 3 个脚本 + 1 个报告目录；`routes/predict.py`、`PredictionResult.vue`、`ml/*`、`test_train_extensions.py` 等**为本任务前既有改动，未触碰** |
| 7 | **工作区是否仍未提交？** | **仍未提交**。HEAD 仍为 `547c55d`；**未执行 `git add` / `git commit` / `reset` / `clean`** |
| 8 | **U6 边牧专项计划文件路径** | `reports/u5_5_v2_1_integration/u6_border_collie_improvement_plan.md` |

---

## 1. 改动范围

### 1.1 核心问题与修复

接入前存在**两个叠加的阻塞点**（经代码审计确认，非猜测）：

1. **`Settings` 没有 `class_names_path`**，`main.py` lifespan 也不透传 →
   `PredictorService` 恒用根目录 `artifacts/class_names.json`（**37 类**）校验，
   加载 136 类 V2.1 必然抛 `class count mismatch`，`/api/predict` 返回 503。
2. **`启动后端.bat` / `启动系统.bat` 硬编码检查 V1.1 文件，且不设任何 `CATDOG_*`** →
   日常入口必然以默认 V1.1 启动。

修复方式（**先加能力、后翻默认**，符合任务单要求的切换顺序）：

| 步骤 | 内容 | 验证 |
|---|---|---|
| 第一步（只加能力） | 新增 `class_names_path` 配置 + `main.py` 透传 + 错配明确失败 + health 增 `model_weights`。**默认值仍指 V1.1** | `250 passed`；`--mode isolated` 用显式 V2.1 路径跑通 **43/43** |
| 第二步（翻默认） | `weights_path` / `class_names_path` → V2.1 目录；`candidate_group_enabled` → `True` | `--mode default` **43/43**；真实入口 health `136` 类 |
| 第三步 | 更新两个 `.bat`；136 类中文映射 | 页面验收 **23/23 + 4/4** |

### 1.2 默认模型路径（最终态）

```
weights_path      = artifacts/v2_1_136classes_seed42/best_model.pth
class_names_path  = artifacts/v2_1_136classes_seed42/class_names.json
candidate_group_enabled = True
```

对应环境变量：`CATDOG_WEIGHTS_PATH` / `CATDOG_CLASS_NAMES_PATH` /
`CATDOG_CANDIDATE_GROUP_ENABLED`（均可显式覆盖，启动脚本**不覆盖**用户设置）。

---

## 2. 模型身份与类别数（运行证据）

### 2.1 真实日常启动入口

```
$ cmd /c 启动后端.bat
INFO:     class mapping verified against class_names.json (136 classes)
INFO:     model ready: version=v2_1_136classes_candidate arch=resnet18 classes=136 device=cuda (weights: best_model.pth)

$ Invoke-RestMethod http://127.0.0.1:8000/api/health
{"status":"ok","model_loaded":true,"num_classes":136,"model_weights":"best_model.pth",
 "model_error":null,"version":"1.0.0","time":"2026-10-19T13:56:35+00:00"}
```

> 原始输出留证：`real_launcher_backend_stderr.log` / `real_launcher_backend_stdout.log`

### 2.2 权重与类别表配对

| 检查 | 结果 |
|---|---|
| `class_names.json` 类别数 / 唯一值 | 136 / 136 |
| checkpoint `num_classes` | 136 |
| checkpoint `class_names` 与文件**顺序一致** | **True** |
| `fc.weight` 形状 | `(136, 512)` |
| 37/136 人为错配 | `ValueError: class count mismatch ... (136 classes) ... (37 classes) ...` |

### 2.3 健康接口新增字段

`HealthResponse.model_weights`（`str | None`，默认 `None`）：
显示**实际加载**的权重文件名，只暴露文件名不含绝对路径。默认 `None` 保证旧响应与
旧消费者兼容（`test_health_response_model_weights_is_optional` 固化）。

> **注意**：V1.1 与 V2.1 的权重文件同名（都是 `best_model.pth`），
> 因此**判断版本必须看 `num_classes`**，不能只看 `model_weights`。

---

## 3. 四类候选功能状态

| 项目 | 值 |
|---|---|
| 默认开关 | **`True`**（接入前为 `False`） |
| 成员 | APBT / AmStaff / SBT / American Bulldog（**未改动**） |
| 阈值 | `mass ≥ 0.30`、`margin ≤ 0.40`（**未重新扫描**） |
| `threshold_version` | `val-2026-10-19-four-breed-b1`（**未变**） |
| 显式关闭 | `CATDOG_CANDIDATE_GROUP_ENABLED=false` → 候选区消失，原始 Top-1/Top-K 逐位不变 |
| V1.1 回退时 | `candidate_group = null`（37 类缺 APBT/AmStaff → 安全返回空，**不崩溃**） |
| 是否写库 | **否**。DB 表字段仍为 `id/image_path/predicted_breed/confidence/top_k_json/inference_ms/created_at` |

---

## 4. 136 类中文映射

| 指标 | 值 |
|---|---|
| 映射条目 | **136**（按 `class_names.json` 顺序） |
| 键唯一 / 中文名唯一 | 136 / 136 |
| 缺失映射 | **0** |
| 含非中文字符的显示名 | **0** |
| 旧 37 类中文名是否改变 | **未改变**（逐项比对通过） |
| 候选四类名称与面板一致 | 是（美国比特斗牛梗 / 美国斯塔福郡梗 / 斯塔福郡斗牛梗 / 美国斗牛犬） |
| 边牧 / 柯利 / 边境梗 | 边境牧羊犬 / 柯利牧羊犬 / 边境梗（**互不混淆**） |
| `BREED_MAPPING_SIZE` | **136**（测试同步更新，同时保留 V1.1 37 类子集兼容断言） |

### 4.1 已审核目录的两处缺陷（本轮显式修补，**逐项列出**）

`reports/v2_class_catalog.csv` 中以下两个类别的 `chinese_name` 实际是**英文**，
直接使用会让界面退化成英文下划线标签：

| canonical label | catalog 原值 | 本轮采用 | 依据 |
|---|---|---|---|
| `basenji` | `basenji` | **巴辛吉犬** | Basenji 的通行中文犬种名 |
| `sealyham_terrier` | `Sealyham_terrier` | **西里汉梗** | Sealyham Terrier 的通行中文犬种名 |

修补集中在 `scripts/generate_breed_mapping.py` 的 `CATALOG_NAME_OVERRIDES`
（含说明），并在 `breed_mapping_audit.csv` 的 `name_source=curated_override` 与
`note` 列中逐项标记，**未做静默填充**。建议后续更新
`reports/v2_class_catalog.csv` 时一并修正这两行。

---

## 5. 测试与验收结果（全部实际执行）

### 5.1 回归

| 命令 | 结果 |
|---|---|
| `.venv\Scripts\python.exe -m pytest tests/ -q` | **250 passed**（基线 244 + 新增 6） |
| `cd frontend; npm test` | **79 passed / 11 files** |
| `cd frontend; npm run build` | **成功**（`built in 855ms`） |

### 5.2 隔离 / 默认配置 API 验收

| 模式 | 结果 | 文件 |
|---|---|---|
| `--mode isolated`（显式 V2.1 注入，默认尚未切换时） | **43 / 43** | `acceptance_v2_1_isolated.json` |
| `--mode default`（默认配置，切换后） | **43 / 43** | `acceptance_v2_1_default.json` |

覆盖：APBT/AmStaff 竞争、APBT 为 Top-1、SBT 为 Top-1、非候选猫、开关关闭、
同图 5 次一致性、AmBull 函数级补测、health 三项。

**同图 5 次一致性**（`same_image_repeated_requests_default.csv`）：
`triggered` 全 True、候选顺序全同、Top-1 标签全同、
**Top-1 分数 `max_abs_diff = 0.000e+00`**、组内得分和 `[100.0 ×5]`。

### 5.3 真实浏览器验收（Playwright + 系统 Chrome）

| 场景 | 结果 |
|---|---|
| 1. APBT/AmStaff 竞争 → 四候选 + 中文名 + 得分和 100.01% + Top-K 不变 | PASS |
| 2. APBT 为 Top-1 → 候选含 APBT、原始分 46.72% 不变 | PASS |
| 3. 用户选择第 2 个候选 → 独立显示「未被替换」、Top-K 未变 | PASS |
| 4. SBT 为 Top-1 → 四候选、得分和 100.00% | PASS |
| 5. 非候选猫 → 无候选区、显示「阿比西尼亚猫」 | PASS |
| 6. 136 类中文名 → 所有 Top-K 主标签无 `_` | PASS |
| 7. 关闭开关重启 → 候选区消失、Top-1 仍为「美国比特斗牛梗」 | PASS |
| **合计** | **23/23（开启）+ 4/4（关闭）** |

截图：`screenshots/01…06*.png`（6 张，全页）。

### 5.4 回退实测

| 项目 | 结果 |
|---|---|
| `/api/health` | `num_classes: 37`、`model_weights: best_model.pth` |
| 后端日志 | `class mapping verified against class_names.json (37 classes)`、`model ready: version=v1_1_37_optimized ... classes=37` |
| 预测一次 | HTTP 200，`top1 = american_bulldog 0.644206`，**`candidate_group = None`** |
| 存储 | `runtime_rollback/`（隔离），正式 DB 未写入 |

---

## 6. 保护结果

| 检查项 | 结果 |
|---|---|
| V1.1 `artifacts/best_model.pth` | `89ef468f199c6d1550fec2638c5ea6f8ef7ad543e57f8ec82c4263c121b1a256` **一致** |
| V1.1 `class_names.json`（37 类）/ `model_version.json` / `experiment_config.json` | SHA256 **一致** |
| V2.1 `best_model.pth` / `class_names.json` / `model_version.json` / `experiment_config.json` | SHA256 **一致**（只读加载） |
| V1 备份（`backup_v1_20261018/`、`v1_1_37_optimized/`） | **一致** |
| `data/processed`、`processed_clean`、`raw`、`v2_processed`、`v2_processed_prev` | 文件数与总字节 **一致** |
| 正式 `data/app.db` | **142 条**，`integrity_check: ok`（隔离验收未写正式库） |
| 项目 `uploads/` | **142 文件**，一致 |
| 训练 | **未运行任何训练脚本，未生成 V2.2 权重** |
| test split | **访问次数 0**（全部样本来自 `data/v2_processed/val`） |
| 既有报告目录 | 全部文件数不变（未被覆盖） |
| 后台进程 | 8000 / 5173 均已释放 |

前后快照：`protection_snapshot_before.json` / `protection_snapshot_after.json`
（`scripts/diagnostic_protection_snapshot.py` 自动比对：**全部受保护对象一致**）。

---

## 7. 逐文件变更清单

### 7.1 本轮（U5.5）修改

| 文件 | 改动 |
|---|---|
| `backend/app/config.py` | 新增 `DEFAULT_MODEL_DIR` + `class_names_path`（env）；默认模型指向 V2.1；候选开关默认 `True` |
| `backend/app/main.py` | 透传 `class_names_path`；health 返回 `model_weights`；错配错误明确化 |
| `backend/app/schemas.py` | `HealthResponse.model_weights`（可选，默认 None） |
| `backend/app/services/predictor.py` | 类别数错配抛含两侧计数与两路径的清晰错误 |
| `frontend/src/utils/breedNames.js` | `BREED_NAMES_ZH` 37 → **136** 条 |
| `frontend/tests/breedNames.test.js` | 136 完整性 / 唯一性 / 旧 37 兼容 / 边牧三类别 / 候选四类 |
| `frontend/tests/historyView.test.js` | 回退用例改用未知标签；新增新旧类别中文显示用例 |
| `tests/test_api.py` | `FakePredictor.weights_path`；health 相关 3 个断言 |
| `tests/test_predictor_service.py` | 数量错配 2 个用例 |
| `tests/test_candidate_group.py` | 默认值断言更新 + `class_names_path` 3 个用例 |
| `启动后端.bat` | 检查 V2.1 两文件、附回退提示、尊重 `CATDOG_*` |
| `启动系统.bat` | 同上 |
| （`启动前端.bat`） | **未修改** |

### 7.2 本轮新增

`scripts/generate_breed_mapping.py`、`scripts/accept_v2_1_integration.py`、
`scripts/page_accept_v2_1_integration.mjs`、`reports/u5_5_v2_1_integration/`

### 7.3 任务前已存在、本轮**未触碰**

`backend/app/routes/predict.py`、`frontend/src/components/PredictionResult.vue`、
`backend/app/services/candidate_group.py`（未跟踪）、`ml/predict.py`、
`ml/predictor.py`、`ml/train.py`、`tests/test_train_extensions.py`、
`frontend/tests/predictionResult*.test.js`、其余 `scripts/*` 与 `reports/v2_1_*`。

> 详细对照见 `diff_summary.md`、`git_status_before.txt` / `git_status_after.txt`、
> `git_diff_before.txt`。

---

## 8. 输出文件

| 文件 | 内容 |
|---|---|
| `integration_report.md` | 本报告 |
| `model_path_audit.md` | 启动脚本、权重/类名路径、环境变量审计 |
| `breed_mapping_audit.csv` | 136 类逐项审计（label / 中文名 / 来源 / 核验 / 备注） |
| `rollback.md` | 已实测的回退手册 |
| `u6_border_collie_improvement_plan.md` | U6/V2.2 边牧专项计划 |
| `acceptance_checklist.md` | D1–D4 逐项验收表 |
| `diff_summary.md` | 变更清单与既有改动区分 |
| `acceptance_v2_1_isolated.json` / `_default.json` | API 验收明细（各 43 项） |
| `same_image_repeated_requests_*.csv` | 同图 5 次 + 开关关闭逐次记录 |
| `page_acceptance_on.json` / `_off.json` | 浏览器验收明细 |
| `screenshots/01…06*.png` | 6 张全页截图 |
| `real_launcher_backend_stdout.log` / `_stderr.log` | 真实入口启动日志留证 |
| `protection_snapshot_before.json` / `_after.json` | 保护快照 |
| `git_status_before.txt` / `git_status_after.txt` / `git_diff_*.txt` | 工作区副本 |
| `default_config_before.json` | 切换前的默认配置留档 |
| `runtime_*/` | 隔离运行的临时 SQLite + uploads（**非正式路径**） |

---

## 9. 已知限制与遗留问题

1. **`model_weights` 无法单独区分版本**：V1.1 与 V2.1 权重同名，必须结合
   `num_classes` 判断。已在 `rollback.md` 与本节明确写出。
2. **American Bulldog 无 val 触发样本**：val 中 9 张 Top-1=AmBull，**0 张**满足
   B1 阈值。因此 D2-3 的 AmBull 部分改用函数级合成样本验证，**未编造样本、未调阈值**。
3. **候选触发率仍低**（val 四类 B1 约 12/2,079 ≈ 0.58%），是既有保守设计的延续。
4. **`basenji` / `sealyham_terrier` 的中文名是脚本内的显式覆盖**，
   源头 `reports/v2_class_catalog.csv` 仍是英文，建议后续修正该目录。
5. **V2.1 的 `model_version.json` 未被改写**（仍在其自身目录内），
   健康接口的版本号来自后端启动日志而非 API 字段；若需要 API 直接返回版本 ID，
   可后续评估给 `HealthResponse` 再加可选字段。
6. **前端无独立候选开关**：仍按后端返回的 `candidate_group.triggered` 自适应渲染。
7. **未做并发压测**：同图一致性为串行请求。
8. **U6 边牧改进未开始**：仅产出计划，样本量极小（val/test 每类 15–16 张）是最大风险。

---

## 10. 工作区状态

**HEAD 仍为 `547c55d`，工作区未提交。**
本轮**未执行** `git add` / `git add .` / `git commit` / `git reset --hard` / `git clean` /
大范围 `checkout`；未删除任何数据目录、权重或既有报告；
未清理任何临时产物（`runtime_*/` 保留，便于人工复核）。
