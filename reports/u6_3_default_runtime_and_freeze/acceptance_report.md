# U6.3：默认启动行为核验与安全固化 — 验收报告

> **报告目录**：`reports/u6_3_default_runtime_and_freeze/`（15 个文件 + 4 张截图 + 3 个隔离 runtime 目录）
> **生成时间**：2026-10-21
> **HEAD**：`547c55d v2训练前`（**未执行任何 Git 写操作**）
> **test split 访问次数 = 0**（所有样本均来自 `data/v2_processed/val`）
> **正式 `data/app.db` / `uploads/` 写入次数 = 0**

---

## 0. 结论摘要

| 问题 | 结论 |
|---|---|
| 日常默认启动配置下，模型实际是不是 V2.1 136 类？ | **是**。`/api/health` → `num_classes: 136`；真实入口启动日志 `model ready: version=v2_1_136classes_candidate arch=resnet18 classes=136` |
| 默认候选总开关有效值？来自哪里？ | **True**，来自 `config.py` 类默认值——**启动脚本不设置任何 `CATDOG_*` 变量** |
| 默认运行时四类 bully 是否触发？ | **是**，8/8 已知触发样本全部触发，1/1 已知不触发样本正确不触发 |
| 默认运行时 `collie-pair` 是否触发？ | **是**，3/3 已知触发样本全部触发，2/2 已知不触发样本正确不触发 |
| 显式关闭总开关后原始预测是否保持不变？ | **是**，14/14 样本原始 Top-1 / Top-K / 分数**逐位一致** |
| 默认配置与既有报告是否有差异？ | **无差异**。U5.5 / U5.2 / U6.2 报告记录的默认模型、开关、阈值与版本全部与实测一致 |
| 保护对象是否全部一致？ | **是**，前后快照自动比对全部一致 |
| 回归是否全部通过？ | **是**，pytest 265 / npm test 85 / build 成功 |

---

## 1. 四层概念的严格分离（任务 §1-A1 核心要求）

任务明确要求"不得仅凭配置文件中的 True/False 就宣称功能已启用或关闭"。
下表把四个概念**分别**记录，证据见 `runtime_config_evidence.json`。

| 层 | 内容 | 实测值 | 证据来源 |
|---|---|---|---|
| **① 配置默认值** | `Settings()` 类默认（不经环境变量） | `weights_path` / `class_names_path` → `artifacts/v2_1_136classes_seed42/`；`candidate_group_enabled = **True**` | `backend/app/config.py` + 进程内 `Settings()` |
| **② 启动脚本显式设置的值** | 三个 `.bat` 中 `set` 的 `CATDOG_*` | **无**——三个脚本均不设置任何 `CATDOG_*` 变量 | 正则扫描 `启动后端.bat` / `启动系统.bat` / `启动前端.bat` |
| **③ 进程实际读取的有效值** | `Settings.from_env()` | 与 ① **完全一致**（`matches_config_defaults: true`） | 同进程解析 |
| **④ API 实际返回的行为** | `/api/health` + 真实上传 | `num_classes: 136`、`model_loaded: true`、候选按 Top-1 分发 | 隔离实例实测 |

**② 的关键细节**：`启动后端.bat` 与 `启动系统.bat` 只在 `if not defined CATDOG_WEIGHTS_PATH` /
`if not defined CATDOG_CLASS_NAMES_PATH` 中**读取**这两个变量，用于决定是否检查 V2.1
默认路径，并在定义时回显；`启动后端.bat` 另在错误提示中提及 `CATDOG_DEVICE`。
**没有任何脚本设置候选开关**，因此日常启动时 ③ 必然等于 ①。

---

## 2. 模型版本的可验证证据（解决同名文件歧义）

`/api/health` 返回 `model_weights: "best_model.pth"`，但 **V1.1 与 V2.1 的权重文件名相同**，
文件名本身**不足以**判定版本。本次用三条独立证据交叉确认：

| 证据 | 值 | 来源 |
|---|---|---|
| `/api/health` 的 `num_classes` | **136**（V1.1 为 37） | 隔离实例 + 真实入口 |
| 后端启动日志 | **`model ready: version=v2_1_136classes_candidate arch=resnet18 classes=136 device=cuda (weights: best_model.pth)`** | `real_launcher_stderr.log` |
| 类名校验日志 | `class mapping verified against class_names.json (136 classes)` | `real_launcher_stderr.log` |
| V2.1 checkpoint SHA256 | `423e218a29230f8248e071e7fb47b88afb2c1f2b67fb860224f6f319041821e1`（与保护快照一致） | `protection_snapshot_*` |

**结论：日常入口实际加载的是 V2.1（136 类），`version=v2_1_136classes_candidate`。**

---

## 3. 阶段 A2：默认配置隔离实例（14 张真实 validation 样本）

**环境**：不修改任何配置文件；仅通过 `CATDOG_DB_PATH` / `CATDOG_UPLOAD_DIR`
把存储重定向到 `runtime_default/`，用 `uvicorn backend.app.main:app` 起进程——
**与日常启动入口同一套 `Settings.from_env()` 解析路径**。

`/api/health`：`num_classes=136`、`model_weights=best_model.pth`、`model_loaded=true`、`model_error=null`。

### 3.1 逐样本结果（`default_runtime_samples.csv`）

| 组 | 真实标签 | 原始 Top-1 | 原始分数 | 候选组 ID | 触发 |
|---|---|---|---|---|---|
| collie-pair-trigger | border_collie | border_collie | 0.6004 | `collie-pair` | **True** |
| collie-pair-trigger | border_collie | **collie** | 0.6032 | `collie-pair` | **True** |
| collie-pair-trigger | border_collie | border_collie | 0.4107 | `collie-pair` | **True** |
| collie-pair-non-trigger | afghan_hound | collie | 0.6391 | `collie-pair` | False |
| collie-pair-non-trigger | bernese_mountain_dog | border_collie | 0.6180 | `collie-pair` | False |
| four-breed-trigger | american_pit_bull_terrier | american_pit_bull_terrier | 0.4672 | `four-breed-bully` | **True** |
| four-breed-trigger | american_staffordshire_terrier | american_pit_bull_terrier | 0.6086 | `four-breed-bully` | **True** |
| four-breed-trigger | american_staffordshire_terrier | american_pit_bull_terrier | 0.6195 | `four-breed-bully` | **True** |
| four-breed-trigger | american_staffordshire_terrier | american_staffordshire_terrier | 0.4659 | `four-breed-bully` | **True** |
| four-breed-trigger | american_staffordshire_terrier | american_staffordshire_terrier | 0.5292 | `four-breed-bully` | **True** |
| four-breed-trigger | bull_mastiff | american_pit_bull_terrier | 0.4707 | `four-breed-bully` | **True** |
| four-breed-trigger | bull_mastiff | american_staffordshire_terrier | 0.4570 | `four-breed-bully` | **True** |
| four-breed-non-trigger | american_bulldog | american_bulldog | 0.9979 | `four-breed-bully` | False |
| control（对照组） | beagle | beagle | 0.9869 | `four-breed-bully` | False |

**触发统计**：collie-pair **3/3**、四类 **8/8**、不触发样本 **3/3 正确不触发**、
对照组 **不触发**。

### 3.2 候选组内相对得分（由完整 Softmax 归一化，非硬编码 50/50）

**collie-pair**（三项）：

| 原始 Top-1 | 得分 |
|---|---|
| border_collie | 边境牧羊犬 **60.0923%** / 柯利牧羊犬 **39.9077%** |
| collie | 柯利牧羊犬 **60.4038%** / 边境牧羊犬 **39.5962%** |
| border_collie | 边境牧羊犬 **72.1898%** / 柯利牧羊犬 **27.8102%** |

**四类 bully**（8 项均和 ≈ 100，示例）：

| 原始 Top-1 | 得分 |
|---|---|
| APBT | APBT **54.4621%** / AmStaff **45.5313%** / SBT **0.0045%** / AmBull **0.0021%** |
| AmStaff | AmStaff **81.8986%** / APBT **17.8530%** / AmBull **0.2468%** / SBT **0.0016%** |

---

## 4. 阶段 A2b：显式关闭对照（**override_test = true**）

> **本节是覆盖配置的独立测试，不是日常默认行为。**
> 通过 `CATDOG_CANDIDATE_GROUP_ENABLED=false` 起**另一个**隔离实例复测同样 14 张图。

| 核验项 | 结果 |
|---|---|
| 关闭实例 `candidate_group` | **14/14 全部为 `None`**（两类候选区域均不返回） |
| 原始 Top-1 标签一致 | **14/14** |
| 原始 Top-K 全部标签与顺序一致 | **14/14** |
| 原始 Top-K 全部分数（8 位小数）逐位一致 | **14/14** |

证据：`switch_off_comparison.json`（含每张图的开启/关闭分数字符串对照）。

**结论：关闭候选总开关只影响候选提示的展示，原始模型预测逐位不变。**

---

## 5. 阶段 A3：UI 语义核验（Playwright + 系统 Chrome，28/28）

隔离后端（默认配置 + `runtime_web/` 存储）+ 真实 Vite 前端 + 系统 Chrome。

| 场景 | 检查项 | 结果 |
|---|---|---|
| 1. collie-pair 触发图 | 双候选区出现、`group_id=collie-pair`、候选行 2、中文名「柯利牧羊犬/边境牧羊犬」、得分和 **100.0000%**、副标题如实、图例含「候选组内相对得分」+ `val-2026-10-21-collie-pair-v1`、「不是整体识别置信度」、「**不保证候选中一定包含正确品种**」、Top-K 仍 3 行 | **11/11** |
| 2. 用户选择交互 | 「你选择的品种」出现、选择值 = 第 2 候选、提示「未被替换」、Top-1 标签不变、Top-1 分数文本不变（60.32% → 60.32%）、Top-K 全部不变 | **6/6** |
| 3. collie-pair 不触发图 | 候选区完全不出现、无「你选择的品种」、Top-K 3 行、Top-1「柯利牧羊犬」、**未按毛色直接触发** | **5/5** |
| 4. 四类 bully 触发图 | 四类候选区出现、`group_id=four-breed-bully`、候选行 4、得分和 **99.9900%**、版本 `val-2026-10-19-four-breed-b1`、**两类策略版本未混用** | **6/6** |

截图：`screenshots/01_pair_trigger.png`、`02_user_selection.png`、
`03_pair_non_trigger.png`、`04_bully_trigger.png`。
明细：`page_probe.json`。

---

## 6. 阶段 B：保护核验（全部一致）

`protection_snapshot_before.json` / `_after.json` 自动比对结果：**全部受保护对象一致**。

| 检查项 | 结果 |
|---|---|
| V1.1 `artifacts/best_model.pth` | `89ef468f…a256` **一致** |
| V2.1 `best_model.pth` | `423e218a…21e1` **一致** |
| V2.1 `class_names.json` / `model_version.json` / `experiment_config.json` | **一致**（只读加载） |
| 五个数据目录 | 文件数与总字节 **一致** |
| 正式 `data/app.db` | **142 条**，`integrity_check: ok`（**写入 0 次**） |
| 项目 `uploads/` | **142 文件**（**写入 0 次**） |
| 默认 `weights_path` / `class_names_path` / `candidate_group_enabled` | V2.1 / V2.1 / **True**，**未改** |
| U6 / U6.1 / U6.2 / U5.5 报告目录文件数 | 53 / 55 / 15 / 23，**全部不变** |
| 训练 | **未运行任何训练脚本** |
| 后台进程 | 8000 / 5173 **已释放** |

---

## 7. 阶段 C：工作区与 Git 变更审计（不写 Git）

### 7.1 规模

| 项目 | 值 |
|---|---|
| HEAD | `547c55d v2训练前` |
| 已跟踪文件被修改 | **18** |
| 未跟踪项 | **83** |
| **合计** | **101** |

原文留存：`git_status_before.txt`、`git_diff_stat_before.txt`、
`git_diff_name_only_before.txt`；逐文件明细：`git_change_inventory.csv`。

### 7.2 七组分类结果

| 组 | 文件数 | 说明 |
|---|---|---|
| G1 U5.5 默认模型接入与 136 类中文名 | 9 | `config.py`、`main.py`、`schemas.py`、`predictor.py`、`breedNames.js`、两个前端测试、两个 `.bat` |
| G2 U5.2 四类候选策略 | 8 | `routes/predict.py`、`candidate_group.py`、`PredictionResult.vue`、3 个前端测试、2 个后端测试 |
| G3 U6.2 collie-pair 候选策略 | 2 | `test_collie_pair_candidate.py`、`colliePairCandidate.test.js`（均为新增） |
| G4 训练基础设施修复（U4/U6-C） | 4 | `ml/train.py`、`ml/dataset.py`、`ml/u6_pair_training.py`、`test_train_extensions.py` |
| G5 验收与诊断脚本 | 约 40 | `scripts/` 下历次验收、诊断、评估脚本 |
| G6 报告/截图/CSV/临时 runtime/冒烟产物/checkpoint | 约 35 | `reports/`、`artifacts/`、`md/` 等 |
| G7 无法明确归属或更早任务的既有改动 | 2 | `ml/predict.py`、`ml/predictor.py` |

（精确计数见 `git_change_inventory.csv` 的 `task_group` 列。）

### 7.3 **混合改动文件（10 个，必须点名）**

任务 §3-C2 要求"若某个已修改文件混合包含多个任务的改动，必须指出，不能声称可以按任务
简单拆分提交"。以下 10 个文件**含多个任务的混合改动**：

| 文件 | 混合来源 |
|---|---|
| `backend/app/main.py` | U5.5 `class_names_path` 透传 + health `model_weights`；U5.2 候选组接线 |
| `backend/app/services/predictor.py` | U5.5 错配明确失败（含两侧计数）；U5.2 `probabilities` 透传 |
| `frontend/src/components/PredictionResult.vue` | U5.3 图例候选数量动态化；U6.2 `group_id` + 副标题 + "不保证候选中一定包含正确品种"；U5.2 既有候选区 |
| `frontend/tests/breedNames.test.js` | U5.5 136 类映射 + 旧 37 兼容；U5.2 候选四类断言 |
| `frontend/tests/historyView.test.js` | U5.5 136 类中文名；U5 既有 |
| `ml/dataset.py` | U6-C `image_size` 参数；U4 既有 |
| `ml/train.py` | U6-C pair-only 训练通道 + `--image-size`；U6 warm-start 分类头继承修复；U4 训练扩展 |
| `tests/test_api.py` | U5.5 health `model_weights` 断言；U5.2 候选组响应断言 |
| `tests/test_predictor_service.py` | U5.5 `class_names_path` 与错配失败用例；U5.2 候选组安全返回 |
| `tests/test_train_extensions.py` | U6-C 训练能力；U4 既有 |

**因此本报告不声称工作区可按任务干净切分**；`recommended_commit_plan.md` 采用
「整文件提交 + commit message 列明覆盖范围」策略。

### 7.4 固化建议要点

`recommended_commit_plan.md` 给出 5 个建议分组（A 生产代码 / B 配套测试 /
C 启动脚本 / D 训练工具独立成组 / E 任务单文档）与「不提交」清单
（`artifacts/`、`reports/`、`data/`、`uploads/`、`.cache/`）。

**关于 `reports/`**：任务要求不得仅因位于 `reports/` 就全部提交或全部排除。
本仓库 `reports/` 在 git 历史中**从未被跟踪**（当前全部为未跟踪项），
故建议**维持既有惯例：不提交**；若希望入库需单独决定并考虑体积。

**所有 `git add` / `git commit` 命令均未执行**，仅作为建议文本写入报告。

---

## 8. 逐条回答任务 §6 的 10 个必答问题

**① 默认日常启动配置下，模型实际是不是 V2.1 的 136 类模型？证据是什么？**
**是。** 三条独立证据：a) 隔离实例与真实入口的 `/api/health` 均返回
`num_classes: 136`；b) 真实入口（`cmd /c 启动后端.bat`）启动日志
`model ready: version=v2_1_136classes_candidate arch=resnet18 classes=136 device=cuda`
（`real_launcher_stderr.log`）；c) `class mapping verified against class_names.json
(136 classes)`。注意 `model_weights` 字段只给文件名 `best_model.pth`，
**V1.1 与 V2.1 同名，不能单独作为版本证据**——版本判定依赖 `num_classes` + 启动日志。

**② 默认开关的有效值是什么？它来自 config、启动脚本还是环境变量？**
**`candidate_group_enabled = True`，来自 `config.py` 的类默认值。**
启动脚本**不设置**任何 `CATDOG_*` 变量（只在 `if not defined` 中读取
`CATDOG_WEIGHTS_PATH` / `CATDOG_CLASS_NAMES_PATH`），因此日常启动时进程有效值
等于配置默认值。覆盖规则：`CATDOG_CANDIDATE_GROUP_ENABLED` 显式
`0/false/no/off` → False，`1/true/yes/on` → True，其它值回退默认 True。

**③ 默认运行时四类 bully 候选和 `collie-pair` 各自是否会触发？真实样本证据？**
**都会触发。** collie-pair **3/3** 已知触发样本触发（`n02106166_416/549/884.jpg`），
2/2 已知不触发样本正确不触发（`afghan_hound`、`bernese_mountain_dog`，Top-1 属两类但
margin 分别 0.6297 / 0.3957 > 0.30）；四类 **8/8** 已知触发样本触发，1/1 已知不触发
（`american_bulldog_119.jpg`，margin 0.9963）正确不触发；对照组 `beagle` 不触发。
逐样本明细见 `default_runtime_samples.csv`。

**④ 显式关闭候选总开关后，原始预测是否保持不变？**
**是，逐位不变。** 14/14 样本的原始 Top-1 标签、Top-K 全部标签与顺序、
Top-K 全部分数（8 位小数字符串）在开启与关闭实例间完全一致；
关闭实例 `candidate_group` 全部为 `None`。证据：`switch_off_comparison.json`。

**⑤ 是否有默认配置与 U5.5/U5.2/U6.2 报告之间的差异？**
**无差异。** 逐项核对：默认模型 V2.1 136 类（U5.5 记录一致）；
候选总开关默认 True（U5.5 记录一致）；四类成员/阈值 `mass 0.30` / `margin 0.40` /
版本 `val-2026-10-19-four-breed-b1`（U5.2 记录一致）；
collie-pair 成员/阈值 `mass 0.30` / `margin 0.30` / 版本 `val-2026-10-21-collie-pair-v1`
（U6.2 记录一致）；V1.1 安全退回（两类均返回 `None`，函数级验证一致）。

**⑥ 所有保护对象是否保持一致？若不一致，具体差异是什么？**
**全部一致**，无差异。见第 6 节表格（V1.1 / V2.1 / 五数据目录 / SQLite 142 条 ok /
uploads 142 / 默认三配置 / 既有报告目录文件数）。

**⑦ 当前工作区有哪些文件属于正式运行必需代码，哪些属于训练工具、诊断工具或实验产物？**
- **正式运行必需**（`runtime_required=yes`）：`backend/app/{config,main,schemas}.py`、
  `backend/app/services/{predictor,candidate_group}.py`、`backend/app/routes/predict.py`、
  `frontend/src/utils/breedNames.js`、`frontend/src/components/PredictionResult.vue`；
- **训练工具**：`ml/train.py`、`ml/dataset.py`、`ml/u6_pair_training.py`、
  `tests/test_train_extensions.py`（**独立成组，不与候选功能混提**）；
- **诊断/验收脚本**：`scripts/` 下约 40 个；
- **实验产物（不提交）**：`artifacts/`（含 V2.2 实验权重）、`reports/`、`data/`、
  `uploads/`、`.cache/`。
精确判定见 `git_change_inventory.csv` 的 `runtime_required` 列。

**⑧ 建议如何分组固化代码？是否存在无法安全按任务切分的混合改动？**
**存在。** 10 个文件含多任务混合改动（见 7.3 表），**不可按任务简单拆分**。
建议分 5 组（A 生产代码 → B 配套测试 → C 启动脚本 → D 训练工具 → E 任务单），
混合文件采用「整文件提交 + commit message 列明覆盖范围」。
命令示例见 `recommended_commit_plan.md`（**均未执行**）。

**⑨ 后端测试、前端测试和构建是否全部通过？**
**全部通过。** `pytest tests/ -q` → **265 passed**（返回码 0）；
`npm test` → **85 passed / 12 files**（返回码 0）；
`npm run build` → **成功 1.69s**（返回码 0）。与基线完全一致，无回归。
详见 `test_results.md`。

**⑩ 是否访问 test split、训练模型、修改标签/数据、写入正式 DB/uploads 或执行 Git 写操作？**
**全部为否**，基于运行证据：
- test split 访问 **0 次**（所有样本来自 `data/v2_processed/val`，脚本内无 test 路径）；
- 未运行任何训练脚本；
- 未修改任何标签、图片或数据划分；
- 正式 `data/app.db` 仍 **142 条**（写入 0 次，所有上传走 `runtime_*` 隔离 SQLite）；
- 项目 `uploads/` 仍 **142 文件**（写入 0 次）；
- **未执行任何 Git 写操作**（HEAD 仍 `547c55d`；`u6_3_git_inventory.py` 仅用
  `status` / `diff` / `log` / `rev-parse` 只读子命令）。

---

## 9. 限制与未解决事项

1. **`model_weights` 字段无法单独区分版本**：V1.1 与 V2.1 权重文件名同为
   `best_model.pth`。版本判定必须结合 `num_classes` 与启动日志。建议后续在
   checkpoint 元数据或 health 中暴露独立的 `model_version` 标识。
2. **collie-pair 触发率极低**：U6.2 记录 val 上仅 3/2,079（0.14%）。
   **本任务只确认其运行行为，不宣称候选提示提高了分类准确率**，
   也不推断它能解决模型高置信度的错误。
3. **本次样本量有限**：14 张（collie-pair 5 + 四类 9 + 对照 1），非全量巡检。
4. **工作区无法按任务干净切分**：10 个文件含混合改动，需人工决定提交粒度。
5. **`reports/` 是否入库需团队决策**：本仓库历史从未跟踪 `reports/`，本报告建议维持；
   若改变惯例需考虑体积（`u6_border_collie/` 含约 400 KB 的逐图预测 CSV）。
6. **隔离 runtime 目录保留现场**：`runtime_default/`、`runtime_off/`、`runtime_web/`
   含临时 SQLite 与上传副本，按任务要求**未清理**，待人工确认后处理。

---

## 10. 交付物清单（`reports/u6_3_default_runtime_and_freeze/`）

| 文件 | 内容 |
|---|---|
| `acceptance_report.md` | 本报告 |
| `runtime_config_evidence.json` | 四层概念分离（config / launcher / process / env 规则）+ main.py 透传 + 候选分发 + V1.1 退回 |
| `default_runtime_samples.csv` | 28 行（14 样本 × 2 实例）：真实标签/路径/原始 Top-1/原始分数/候选组 ID/触发状态/触发原因/候选组得分 |
| `switch_off_comparison.json` | 关闭开关后 14/14 原始预测逐位一致的对照 |
| `git_change_inventory.csv` | 101 项：路径/tracked/增删行数/任务组/运行时必需/混合改动/提交建议/理由 |
| `git_inventory_summary.json` | 审计汇总（HEAD、计数、混合文件清单、运行时必需清单） |
| `recommended_commit_plan.md` | 5 组固化建议 + 精确路径 + 依赖 + 命令示例（**未执行**） |
| `test_results.md` | 三项回归的命令、返回码、通过数 |
| `protection_snapshot_before.json` / `_after.json` | 保护快照（自动比对一致） |
| `git_status_before.txt` / `git_diff_stat_before.txt` / `git_diff_name_only_before.txt` | Git 原文 |
| `api_health_default.json` / `api_health_off.json` | 两个隔离实例的 health 响应 |
| `runtime_launcher_default.log` / `_off.log` | 隔离实例启动日志 |
| `real_launcher_stdout.log` / `real_launcher_stderr.log` | **真实启动入口**日志（含模型身份证据） |
| `page_probe.json` | 页面语义核验 28 项明细 |
| `screenshots/01–04*.png` | 4 张全页截图 |
| `runtime_default/`、`runtime_off/`、`runtime_web/` | 隔离实例临时 SQLite + uploads（未清理） |

---

## 11. 本轮新增/修改文件

### 新增

| 文件 | 用途 |
|---|---|
| `scripts/u6_3_static_audit.py` | A1 静态配置审计（四层概念前三层） |
| `scripts/u6_3_runtime_probe.py` | A2 隔离实例运行取证（默认 + 显式关闭） |
| `scripts/u6_3_verify_switch_off.py` | 关闭开关后原始预测逐位一致性核验 |
| `scripts/u6_3_git_inventory.py` | C 段 Git 变更审计（只读 git 子命令） |
| `scripts/u6_3_page_probe.mjs` | A3 UI 语义核验（Playwright + 系统 Chrome） |
| `reports/u6_3_default_runtime_and_freeze/` | 本报告目录 |

### 未触碰

`backend/`、`frontend/src/`、`ml/`、`tests/`、`.bat`、`artifacts/`、`data/`、
`data/app.db`、`uploads/`，以及 `reports/u6_border_collie/`、`reports/u6_1_low_lr/`、
`reports/u6_2_collie_pair_candidate/`、`reports/u5_5_v2_1_integration/` 等既有报告目录
（均只读引用）。

---

**已完成验收与固化建议，停止等待人工审核。未启用或关闭任何正式功能开关、未改默认模型、
未训练、未访问 test split、未写正式 DB/uploads、未执行任何 Git 写操作、未清理工作区。**
