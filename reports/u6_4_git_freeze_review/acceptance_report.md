# U6.4：Git 安全固化 — 审核报告

> **阶段性质：只读审核。本轮未执行任何 Git 写操作。**
> HEAD 仍为 `547c55d`，`git diff --cached` 为空，索引与分支未变。
> 完成本报告后**立即停止，等待人工审核批准**。
>
> 报告目录：`reports/u6_4_git_freeze_review/`
> 生成时间：2026-10-21
> 基线快照：`working_tree_before.txt`（开工时）/ `working_tree_after.txt`（收工时）

---

## 0. 总体结论

| 项目 | 结论 |
|---|---|
| **HEAD 是否仍为 `547c55d`** | **是**（完整 SHA `547c55dd96b5d2a9aca71c58458f4192e55b38f5`，分支 `master`） |
| **与 U6.3 基线（18 M / 83 ??）是否一致** | **已跟踪 18 项完全一致**（逐路径比对无新增/消失/状态变化）；未跟踪在扣除本任务自建项后为 **84 = 83 + 本任务单 1**，**唯一外部新增是本任务单自身** |
| **索引是否被修改** | **否**，`git diff --cached` 全程为空 |
| **Git 写操作次数** | **0** |
| **是否执行训练 / 访问 test split / 写正式 DB·uploads** | **全部为否** |
| **混合改动文件** | 任务指定 **10** 个 + 本次额外发现 **4** 个新文件 = **14** 个 |
| **建议提交分组** | **A（10）/ B（9）/ C（2）/ D（4）/ E（12，条件）/ F（不提交）** |
| **必须人工决策的点** | **4 项**（见 §5） |

---

## 1. 只读基线捕获与 U6.3 一致性核验

### 1.1 捕获时点说明（**关键，避免误判为外部变化**）

按任务 §3-A 第 4 条要求"**先记录状态，再创建本轮输出目录**"，本任务的未跟踪计数
经历了三个阶段，**全部来自本任务自身**：

| 时点 | 未跟踪数 | 变化来源 |
|---|---:|---|
| U6.3 inventory（C 阶段） | **83** | U6.3 报告目录 + 5 个 U6.3 脚本 |
| U6.4 开工审计（建目录前） | **84** | **+1 = `md/U6.4_Git安全固化_审核与提交计划.md`**（本任务单，任务下发时已存在） |
| 创建 `scripts/u6_4_capture_baseline.py` 后 | **85** | +1 = 本任务的基线捕获脚本 |
| 创建 `reports/u6_4_git_freeze_review/` 后 | **86** | +1 = 本报告目录 |
| 创建 `scripts/u6_4_git_review.py` 后（当前） | **87** | +1 = 本任务的审阅脚本 |
| **当前合计** | **18 M + 87 ?? = 105** | |

**扣除本任务自建 3 项后 = 84**，其中 **83 与 U6.3 inventory 完全一致**，**1 项为本任务单**。

> ⚠️ **若与 U6.3 的 `git_status_before.txt`（S0 时点，78 个未跟踪）直接比对，会"多出 6 项"**：
> 其中 5 项是 U6.3 在 S0 快照**之后**自己创建的脚本与报告目录，1 项是本任务单。
> **这 6 项均非外部变化**，不得误记为有人改动工作区。

### 1.2 三张差异表（相对 U6.3 inventory）

**表 1：已跟踪修改（18 项）—— 无差异**

| 差异类型 | 数量 | 明细 |
|---|---:|---|
| 新增（U6.3 之后出现） | **0** | — |
| 消失（U6.3 之后不见） | **0** | — |
| 状态变化 | **0** | — |

逐路径比对结果：18 个 ` M` 文件**清单完全一致**，顺序亦一致。

**表 2：未跟踪项 —— 唯一实质新增为本任务单**

| 差异类型 | 数量 | 明细 |
|---|---:|---|
| 新增（外部） | **1** | `md/U6.4_Git安全固化_审核与提交计划.md` |
| 新增（本任务自建） | **3** | `scripts/u6_4_capture_baseline.py`、`scripts/u6_4_git_review.py`、`reports/u6_4_git_freeze_review/` |
| 消失 | **0** | — |

> 比对过程中曾出现"12 个 md 新增 / 12 个 md 消失"的假阳性，
> 根因是 **U6.3 的 `git_change_inventory.csv` 把中文 md 路径写成了八进制转义符**
> （见 §4.2），去引号后仍无法与当前可读路径匹配。逐字节核对后确认是同一批文件。

**表 3：状态变化（同一路径在 M 与 ?? 之间迁移）**

| 差异类型 | 数量 |
|---|---:|
| M → ?? 或 ?? → M | **0** |

### 1.3 索引状态

| 检查 | 结果 |
|---|---|
| `git diff --cached --stat` | **空** |
| `git diff --cached --name-status` | **空** |
| 结论 | 暂存区干净，**无任何被暂存的文件** |

---

## 2. 逐文件审阅（以真实 diff 为准）

### 2.1 规模

| 项目 | 值 |
|---|---|
| `git diff --stat` 合计 | **+1267 / −79**（18 个文件） |
| 逐文件审阅条目（`file_by_file_review.csv` 中 `review_depth` 非空） | **25** |
| 已读**完整** diff（`full-diff`） | 11 |
| 已读 diff **摘要**（`diff-summary`） | 12 |
| 已读**文件首部**（`file-head`） | 2（未跟踪产物目录） |

> 审阅深度如实标注在 CSV 的 `review_depth` 列。
> **未逐一阅读完整 diff 的条目已明确标为 `diff-summary` 或 `file-head`，未假装已读。**

### 2.2 18 个已跟踪修改

| 路径 | 组 | 混合 | +/− |
|---|---|:--:|---:|
| `backend/app/config.py` | A | 否 | +38/−3 |
| `backend/app/main.py` | A | **是** | +18/−1 |
| `backend/app/routes/predict.py` | A | 否 | +11/−0 |
| `backend/app/schemas.py` | A | **是** | +57/−0 |
| `backend/app/services/predictor.py` | A | **是** | +33/−2 |
| `frontend/src/components/PredictionResult.vue` | A | **是** | +242/−1 |
| `frontend/src/utils/breedNames.js` | A | **是** | +133/−11 |
| `ml/predict.py` | A | 否 | +15/−2 |
| `ml/predictor.py` | A | 否 | +8/−3 |
| `frontend/tests/breedNames.test.js` | B | **是** | +90/−17 |
| `frontend/tests/historyView.test.js` | B | **是** | +35/−2 |
| `tests/test_api.py` | B | **是** | +25/−0 |
| `tests/test_predictor_service.py` | B | **是** | +37/−0 |
| `ml/dataset.py` | D | **是** | +15/−7 |
| `ml/train.py` | D | **是** | +289/−18 |
| `tests/test_train_extensions.py` | D | **是** | +181/−1 |
| `启动后端.bat` | C | 否 | +28/−9 |
| `启动系统.bat` | C | 否 | +12/−2 |

### 2.3 关键实测发现

1. **`config.py` 的两个字段在 HEAD 中完全不存在**：`git show HEAD:backend/app/config.py`
   实测确认 HEAD 版本**没有** `class_names_path`，**也没有** `candidate_group_enabled`。
   两者均为工作区新增（U5.5 新增 `class_names_path`，U5.2 新增开关字段、U5.5 将其默认翻为 True）。
   → 因此该文件虽被 U6.3 归入 G1，实际是**纯新增语义、无跨任务混合**。

2. **`ml/predict.py` 与 `ml/predictor.py` 的归属修正**：diff 显示二者仅新增
   `probabilities` 全量 softmax 透传，docstring 明确 "API response schema never exposes it"，
   目的是让候选组不把 Top-K 外候选当作 0 分。
   **U6.3 将其归入 G7「无法明确归属」，实测应归入候选策略组（本报告归 A 组）。**

3. **`predictor.py` 的条件分支设计**：仅在两侧**类别数不同**时才改写错误消息，
   数量相同但名称/顺序不同则保留 `verify_class_mapping` 原有的索引级错误——
   这是为不破坏既有测试刻意设计的。**当前无测试覆盖"数量相同名称不同"这条路径**，
   属未覆盖风险（见 §3）。

---

## 3. 混合改动风险（14 个）

详见 `mixed_changes_analysis.md`（按任务 §3-D 的四维度逐一说明）。

| 类别 | 数量 | 文件 |
|---|---:|---|
| 任务指定的 10 个 | 10 | `main.py`、`predictor.py`、`PredictionResult.vue`、`breedNames.test.js`、`historyView.test.js`、`dataset.py`、`train.py`、`test_api.py`、`test_predictor_service.py`、`test_train_extensions.py` |
| **本次额外发现（新文件）** | **4** | `candidate_group.py`（含两套策略）、`predictionResult.test.js`、`predictionResultAcceptance.test.js`、`test_candidate_group.py` |
| **合计** | **14** | 其中运行必需 5 个 |

### 三条硬结论

1. **不可声称"可按任务干净切分"**：14 个文件含多任务内容；`ml/train.py` 含
   **U4 / U6-C / U6 warm-start 三类来源**（+289/−18，全仓最大单文件改动）；
   `PredictionResult.vue` 含 **U5.2 / U5.3 / U6.2 三轮迭代**且后两轮有直接依赖。
2. **不建议拆分**：除 `PredictionResult.vue` 理论上可用 `git add -p` 外，
   其余跨任务改动在同一函数/同一语义块内交织，拆分成本高、易引入中间状态不一致。
3. **必须人工决策的依赖风险**：`frontend/tests/predictionResultAcceptance.test.js`
   读取 `reports/v2_1_four_breed_candidate_implementation/acceptance_api_responses.json`。
   若坚持 "reports/ 不入库"，该测试在新克隆环境**会失败**。

### 未覆盖风险（新增发现）

| 风险 | 说明 |
|---|---|
| `predictor.py` 的条件分支无测试 | "类别数相同但名称/顺序不同 → 保留原索引级错误"这条路径**当前无覆盖**；若上游改措辞，分支会静默失效 |
| `model_weights` 无法区分版本 | V1.1/V2.1 权重同名 `best_model.pth`；已在 U6.3 记录，属既有设计限制 |
| 4 个脚本含本地绝对路径 | `audit_v2_data_sources.py`、`build_clean_split.py`、`build_v2_dataset.py`、`diagnose_dataset.py` 硬编码 `E:\CatDogBreedNet` |

---

## 4. 对 U6.3 产物的两处修正（**不覆盖 U6.3 文件**）

按任务要求"不应另起炉灶或静默改写历史记录"，以下修正**仅在本次报告中说明**，
`reports/u6_3_default_runtime_and_freeze/` 内**任何文件均未被修改**。

### 4.1 分类修正：`ml/predict.py` / `ml/predictor.py`

| 项目 | U6.3 原结论 | 本次实测结论 |
|---|---|---|
| 分类 | G7「无法明确归属或更早任务的既有改动」 | **候选策略组（本报告 A 组）** |
| 依据 | 未展开 diff | diff 显示仅新增 `probabilities` 全量 softmax 透传，docstring 明确"API schema never exposes it"、目的是让候选组不把 Top-K 外候选当 0 |

### 4.2 数据质量修正：U6.3 inventory CSV 的中文路径损坏

| 项目 | 说明 |
|---|---|
| 现象 | `git_change_inventory.csv` 中 12 个 `md/*` 路径被写成八进制转义符，如 `md/U5.2_\346\226\207\346\241\210...` |
| 根因 | `scripts/u6_3_git_inventory.py` 用 `subprocess(..., text=True, errors="replace")` 解码 git 输出，非 ASCII 字节被替换成转义序列 |
| 影响 | 路径不可直接用于 `git add`；集合比对时产生"12 新增 / 12 消失"假阳性 |
| 本任务处理 | `scripts/u6_4_git_review.py` 改用 `capture_output` + `decode("utf-8", errors="surrogateescape")`，`file_by_file_review.csv` 中 md 路径**已可读**（见 §7 验证） |
| 建议 | 后续如需再用 U6.3 的 CSV，应先按本任务的方式重新生成，勿直接引用其 md 行 |

---

## 5. 必须人工决策的 4 个点

| # | 决策点 | 选项 | 影响 |
|---|---|---|---|
| **1** | `frontend/tests/predictionResultAcceptance.test.js` 去留 | ①破例提交其依赖的 `reports/.../acceptance_api_responses.json` ②改为内置 fixture（需改代码，本轮不做）③暂不提交该测试 | ①②则测试可用；③则该测试不入库，其余 8 个 B 组文件不受影响 |
| **2** | `md/` 12 个任务单是否入库 | ①整组提交 ②整组排除 | 不影响代码与测试；仅影响仓库文档完整性 |
| **3** | `scripts/` 41 个脚本是否入库 | ①整组暂不提交（本报告建议）②挑选 5 个"候选长期工具"单独讨论 ③全部提交（需先参数化 4 个含本地路径的脚本） | 全部提交会把一次性验收脚本引入长期维护负担 |
| **4** | 是否接受"整文件提交 + message 说明"而非拆分混合改动 | ①接受（本报告建议）②要求拆分（需另行制作独立补丁，成本高） | 拆分 `ml/train.py` 需 3 个补丁且易错 |

---

## 6. 测试核验

### 6.1 引用 U6.3 实测结果（**本轮未重跑**）

按任务 §3-E"可引用 U6.3 的近期测试结果作为基线"，且本轮**未修改任何源代码**，
故引用 `reports/u6_3_default_runtime_and_freeze/test_results.md`（2026-10-21 实测）：

| 命令 | 返回码 | 结果 |
|---|---|---|
| `.venv\Scripts\python.exe -m pytest tests/ -q` | 0 | **265 passed** |
| `cd frontend; npm test` | 0 | **85 passed / 12 files** |
| `cd frontend; npm run build` | 0 | **成功 1.69s** |

**本轮未重跑的理由**：
1. 任务 §3-E 明确允许引用；
2. 本轮**零代码改动**（仅新增 2 个只读审计脚本 + 报告目录），不影响测试结果；
3. 重跑会生成新的 `__pycache__` / `node_modules/.vite` 缓存，而任务要求"测试生成的缓存不得清理"，
   无谓增加工作区噪声。

**如需重跑请人工决定**；建议在真正执行 `git add` 之前重跑一次，作为提交前最后确认。

### 6.2 边界确认

- 未访问 `data/v2_processed/test`
- 未启动训练
- 未写正式 `data/app.db` 与项目 `uploads/`
- 未修改任何模型或阈值

---

## 7. 交付物清单

| 文件 | 内容 | 状态 |
|---|---|---|
| `acceptance_report.md` | 本报告 | ✅ |
| `file_by_file_review.csv` | **105 行**全量路径 × 12 列（path/git_status/tracked/change_summary/task_group/runtime_required/mixed_change/commit_recommendation/reason/added_lines/deleted_lines/review_depth） | ✅ |
| `commit_plan.md` | A/B/C/D/E 五组精确清单、依赖图、建议 commit message、PowerShell 命令（标注未执行、无通配符） | ✅ |
| `do_not_commit.md` | 按类型列出的排除项与理由 | ✅ |
| `working_tree_before.txt` | 开工时只读快照（HEAD/分支/status/diff/cached/未跟踪清单） | ✅ |
| `working_tree_after.txt` | 收工时只读快照 | ✅ |
| **`mixed_changes_analysis.md`** | **补充交付**：14 个混合改动文件的四维度分析（任务 §3-D 要求"逐一说明"，独立成文更易审阅） | ✅ |

**已验证**：`file_by_file_review.csv` 中 12 个 `md/*` 路径均为**可读中文**，
不再是八进制转义符（§4.2 的修正已生效）。

### 分组文件数校验

| 组 | 文件数 |
|---|---:|
| A 正式运行代码 | 10 |
| B 配套测试 | 9 |
| C 启动入口 | 2 |
| D 训练基础设施 | 4 |
| E 任务单（条件） | 12 |
| F 暂不提交 | 68 |
| **合计** | **105** |

---

## 8. 完成前自检（任务 §5 清单逐项闭环）

| # | 自检项 | 结果 | 证据 |
|---:|---|---|---|
| 1 | 解释当前 HEAD 是否仍为 `547c55d` | ✅ **是**，完整 SHA `547c55dd96b5d2a9aca71c58458f4192e55b38f5` | `working_tree_before.txt` §1、`working_tree_after.txt` §1 |
| 2 | 解释 tracked/untracked 与 U6.3 的 18/83 是否一致 | ✅ tracked **18 完全一致**；untracked 83 → 84（**唯一外部新增 = 本任务单**），另 3 项为本任务自建 | 本报告 §1.1、§1.2 |
| 3 | 所有当前变更路径均在 CSV 中有记录 | ✅ **105 行全量覆盖**，无遗漏 | `file_by_file_review.csv` |
| 4 | 10 个混合改动文件逐一说明 | ✅ **10 个全部说明，另加 4 个新增发现** | `mixed_changes_analysis.md` |
| 5 | 每个建议提交组列出确切路径，无模糊通配符 | ✅ A(10)/B(9)/C(2)/D(4)/E(12) 逐条列出，无 `*` | `commit_plan.md` §2–§6 |
| 6 | 不建议 `git add .` 或 `git add -A` | ✅ 全文无这两条命令；`do_not_commit.md` §7 明确禁止 | `commit_plan.md`、`do_not_commit.md` |
| 7 | 训练工具独立于生产运行时代码 | ✅ D 组独立（`ml/train.py`、`dataset.py`、`u6_pair_training.py`、`test_train_extensions.py`），与 A/B/C 无符号依赖 | `commit_plan.md` §5、依赖图 §1 |
| 8 | 权重/数据/DB/上传/缓存/报告/隔离 runtime 默认不提交 | ✅ `artifacts/` 12 项、`reports/` 12 项列入不提交；`.cache/`/`data/`/`uploads/`/`dist` 已被 `.gitignore` 覆盖 | `do_not_commit.md` §1–§3 |
| 9 | `git diff --cached` 前后无变化、HEAD 未变化、未执行任何 Git 写操作 | ✅ 全程 `--cached` 为空；HEAD 不变；**写操作 0 次** | 本报告 §9 |
| 10 | 没有训练、test split 访问、数据修改或正式 DB/uploads 写入 | ✅ 全部为 0 | 本报告 §9 |

---

## 9. 零写操作与保护核验

### 9.1 Git

| 检查项 | 结果 |
|---|---|
| HEAD（收工时） | `547c55dd96b5d2a9aca71c58458f4192e55b38f5` —— **与开工时一致** |
| 分支 | `master` —— 未变 |
| `git diff --cached --stat` | **空** |
| `git diff --cached --name-status` | **空** |
| **Git 写操作** | **0 次**（未 `add`/`commit`/`reset`/`checkout`/`restore`/`clean`/`stash`/`rebase`） |

**本轮实际执行的 Git 命令全清单（均为只读）**：

```
git rev-parse HEAD
git rev-parse --abbrev-ref HEAD
git status --short
git diff --stat
git diff --name-status
git diff --cached --stat
git diff --cached --name-status
git diff --numstat -- <path>
git diff -- <path>
git show HEAD:<path>
git ls-files --others --exclude-standard
git log -n 1 --oneline
```

脚本层另有白名单硬约束：`scripts/u6_4_capture_baseline.py` 与
`scripts/u6_4_git_review.py` 均定义了 `READONLY` 集合，
**任何非白名单子命令在调用前即抛出 `SystemExit`**。

### 9.2 模型与数据

| 检查项 | 结果 |
|---|---|
| V1.1 `artifacts/best_model.pth` | `89ef468f199c6d1550fec2638c5ea6f8ef7ad543e57f8ec82c4263c121b1a256` —— **未变**（未写入） |
| V2.1 四文件 | **未写入**（本轮只读加载 `git show`，未触碰文件系统） |
| 五个数据目录 | **未修改** |
| 正式 `data/app.db` | **142 条**、`integrity_check: ok` —— **未写入** |
| 项目 `uploads/` | **142 文件** —— **未写入** |
| 默认 `weights_path` / `class_names_path` / 候选开关 | V2.1 / V2.1 / True —— **未改** |
| 训练 | **未运行** |
| test split | **访问 0 次** |
| U6.3 隔离 runtime 目录 | **未删除、未清理** |
| `.cache/` / `artifacts/` / `reports/` | **未清理** |
| 源文件编辑或拆分 | **未执行** |

---

## 10. 下一步（需人工批准）

1. **先决策 §5 的 4 个点**（尤其 `predictionResultAcceptance.test.js` 与 `md/`）；
2. 按 `commit_plan.md` 的 A → B → C →（可选 D）→（可选 E）顺序执行；
3. **每组执行后立即** `git diff --cached --name-status` 核对行数与路径，
   再跑一次回归（`pytest` / `npm test` / `npm run build`）；
4. 若暂存区与预期不符 → **立即停止**，先人工核查，不要继续提交下一组。

**建议在执行 `git add` 前重跑一次测试**（本轮按任务允许引用了 U6.3 结果），
作为提交前最后确认。

---

**审核完成，立即停止并等待人工审核。本轮 Git 写操作 0 次、HEAD 未变、索引未变；
未训练、未访问 test split、未修改数据或标签、未写正式 DB/uploads、未清理工作区、
未编辑或拆分任何源文件。**
