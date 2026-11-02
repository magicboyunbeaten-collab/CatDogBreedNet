# U5.5 变更清单与既有改动区分

> 基线：任务开始时记录于 `git_status_before.txt` / `git_diff_stat_before.txt` / `git_diff_before.txt`
> 结束态：`git_status_after.txt` / `git_diff_stat_after.txt`
> **工作区仍未提交，本轮未执行 `git add` / `git commit` / `reset` / `clean`。**

---

## 一、本次 U5.5 修改的文件

| 文件 | 改动要点 |
|---|---|
| `backend/app/config.py` | 新增 `DEFAULT_MODEL_DIR` 常量与 `class_names_path` 字段（env `CATDOG_CLASS_NAMES_PATH`）；默认 `weights_path` / `class_names_path` 指向 V2.1 目录；`candidate_group_enabled` 默认由 `False` 改为 `True`；`from_env()` 同步 |
| `backend/app/main.py` | lifespan 透传 `class_names_path`；`/api/health` 返回 `model_weights`；`_safe_model_error` 对类别数错配给出明确原因（含两侧计数，不泄露绝对路径） |
| `backend/app/schemas.py` | `HealthResponse` 新增可选字段 `model_weights: str \| None = None`（默认 None，向后兼容） |
| `backend/app/services/predictor.py` | 类别**数量**错配时重抛含两个真实路径与两侧计数的清晰错误；数量相同但名称/顺序不同时保留原有索引级消息 |
| `frontend/src/utils/breedNames.js` | `BREED_NAMES_ZH` 由 37 条扩为 **136 条**（按 checkpoint 顺序）；旧 37 条中文名原样保留；`CANDIDATE_BREED_NAMES_ZH`(4) 与 `CANDIDATE_GROUP`(4) 保持不变 |
| `frontend/tests/breedNames.test.js` | 断言改为 136 类完整性 + 唯一性 + 旧 37 类兼容 + 边牧/柯利/边境梗互不混淆 + 候选四类中文名 + 无英文下划线主标签 |
| `frontend/tests/historyView.test.js` | 「未映射标签回退英文原名」改用真正未知的标签（`border_collie` 现已映射为「边境牧羊犬」）；新增「旧 37 类与新 99 类历史标签都能显示中文」 |
| `tests/test_api.py` | `FakePredictor` 增加 `weights_path`；新增 health 回报权重文件名、`model_weights` 可选兼容两个用例；`model_not_ready` 断言 `model_weights is None` |
| `tests/test_predictor_service.py` | 新增 2 个用例：类别数错配必须抛 `ValueError` 且消息含两侧计数与两个文件名；错配不得静默降级 |
| `tests/test_candidate_group.py` | 默认值断言随新默认更新（候选开 = True、默认模型 = V2.1、`garbage` 回退 True）；新增 `class_names_path` 独立配置、env 覆盖、V1.1 文件仍存在 3 个用例 |
| `启动后端.bat` | 存在性检查由 `artifacts\best_model.pth` / `artifacts\class_names.json` 改为 **V2.1 目录下两个文件**；缺失时给明确错误 + 可复制的回退提示；**不设置任何 `CATDOG_*`**，尊重用户显式覆盖 |
| `启动系统.bat` | 同上（启动前检查改为 V2.1 两文件，并附回退提示） |
| `启动前端.bat` | **未修改**（只负责前端，无需模型路径逻辑） |

## 二、本次 U5.5 新增的文件

| 文件 | 用途 |
|---|---|
| `scripts/generate_breed_mapping.py` | 从 `v2_class_catalog.csv` + `class_names.json` 生成 136 条中文映射，内置完整性断言，产出 `breed_mapping_audit.csv` |
| `scripts/accept_v2_1_integration.py` | 隔离环境六场景 API 验收（支持 `--mode isolated` / `--mode default`） |
| `scripts/page_accept_v2_1_integration.mjs` | Playwright + 系统 Chrome 的真实页面验收（on/off 两态、7 场景） |
| `reports/u5_5_v2_1_integration/` | 本报告目录（见集成报告第 8 节） |

## 三、任务开始前**已存在**、本轮未改动的改动（原样保留）

| 文件 | 来源 |
|---|---|
| `backend/app/routes/predict.py` | U5（候选组接线） |
| `frontend/src/components/PredictionResult.vue` | U5 / U5.2 / U5.3（候选区与动态数量文案） |
| `ml/predict.py`、`ml/predictor.py` | U5（完整 softmax 透传） |
| `ml/train.py`、`tests/test_train_extensions.py` | U4（`--init-from` / `--monitor`） |
| `backend/app/services/candidate_group.py`（未跟踪） | U5 / U5.2（四类候选组） |
| `frontend/tests/predictionResult.test.js`、`predictionResultAcceptance.test.js`（未跟踪） | U5 / U5.2 / U5.4 |
| `artifacts/v2_1_136classes_seed42/`、`artifacts/_v2_1_smoke/`（未跟踪） | U4 训练产物 |
| 其余 `reports/v2_1_*` 与 `scripts/*`（未跟踪） | U4 / U5 / U5.1 / U5.2 / U5.3 / U5.4 |

## 四、`git diff --stat` 对比

任务开始时（`git_diff_stat_before.txt`）与结束时（`git_diff_stat_after.txt`）的差异
**仅体现本轮新增的 17 个已跟踪文件改动**；未出现"既有改动被回退"的迹象：

```
 backend/app/config.py                              |  41 +++-
 backend/app/main.py                                |  19 +-
 backend/app/routes/predict.py                      |  11 +      ← 既有（U5）
 backend/app/schemas.py                             |  51 +++++
 backend/app/services/predictor.py                  |  35 +++-
 frontend/src/components/PredictionResult.vue       | 215 ++++   ← 既有（U5~U5.3）
 frontend/src/utils/breedNames.js                   | 144 ++++-
 frontend/tests/breedNames.test.js                  | 107 ++++--
 frontend/tests/historyView.test.js                 |  37 +++-
 ml/predict.py                                      |  17 +-    ← 既有（U5）
 ml/predictor.py                                    |  11 +-    ← 既有（U5）
 ml/train.py                                        | 222 ++++   ← 既有（U4）
 tests/test_api.py                                  |  25 +++
 tests/test_predictor_service.py                    |  37 ++++
 tests/test_train_extensions.py                     | 182 ++++   ← 既有（U4）
 启动后端.bat                                        |  37 +++-
 启动系统.bat                                        |  14 +-
```

> 注：`backend/app/routes/predict.py`、`PredictionResult.vue`、`ml/*`、
> `tests/test_train_extensions.py` 的改动**在本任务开始前就已存在**，
> 本轮未触碰（可用 `git_diff_before.txt` 与 `git_diff_after.txt` 逐文件比对确认）。
