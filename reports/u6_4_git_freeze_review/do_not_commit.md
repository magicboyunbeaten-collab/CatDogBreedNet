# U6.4：明确建议**不提交**的项与理由

> 本文件对应任务 §4 第 4 项与 §5 自检清单。
> 生成时间：2026-10-21
> 依据：`git status --short` 实测 105 行中 `task_group=F` 的 68 项 + 分组 E 的 12 项（条件提交）。

---

## 0. 汇总

| 类型 | 项数 | 结论 |
|---|---:|---|
| 模型权重与实验 checkpoint（`artifacts/`） | 12 | **不提交** |
| 报告/截图/CSV/隔离 runtime（`reports/`） | 12 | **不提交** |
| 验收与诊断脚本（`scripts/`，41 个） | 41 | **本次暂不提交**（见 §4） |
| 缓存与构建产物（`.cache/`、`frontend/dist/`） | 0（已被 .gitignore 覆盖） | **不提交** |
| 数据与上传（`data/`、`uploads/`） | 0（已被 .gitignore 覆盖） | **不提交** |
| 任务单文档（`md/`） | 12 | **条件提交**（见 §5） |
| **合计不提交** | **65** | |

> 68（F 组）+ 12（E 组）= 80，其中 `scripts/` 的 41 与 `md/` 的 12 在分组上分属 F/E，
> 但结论不同（`scripts/` 暂不提交、`md/` 条件提交）。上表按"类型"归并，故合计为 65 项
> 明确不提交 + 12 项条件提交 + 3 项本任务自建产物（见 §6）。

---

## 1. 模型权重与实验 checkpoint（`artifacts/`，12 项）——**硬禁止**

**明确不提交**：`artifacts/` 下全部内容。

| 路径 | 内容 | 不提交理由 |
|---|---|---|
| `artifacts/_v2_1_smoke/` | 冒烟训练产物 | 临时产物，无复用价值 |
| `artifacts/v2_1_136classes_seed42/` | **正式默认模型**（V2.1，136 类） | `.pth` 权重约 45 MB/个；任务 §2.2 明确"不得把 `.pth` 加入 Git" |
| `artifacts/v2_2_border_collie_exp01_pair_color_jitter_seed42/` | U6 实验权重 | 同上；且为**未达标**实验结果 |
| `artifacts/v2_2_border_collie_exp02_pair_sampler_seed42/` | U6 实验权重 | 同上 |
| `artifacts/v2_2_border_collie_exp04_resolution_seed42/` | U6 实验权重 | 同上 |
| `artifacts/v2_2_border_collie_exp04_resolution_seed7/` | U6 实验权重 | 同上 |
| `artifacts/v2_2_border_collie_exp04_resolution_seed2024/` | U6 实验权重 | 同上 |
| `artifacts/v2_2_border_collie_exp06_resolution256_lowlr_seed42/` | U6.1 实验权重 | 同上（候选未达标，见 U6.1 报告） |
| `artifacts/v2_2_border_collie_exp06_resolution256_lowlr_seed7/` | U6.1 实验权重 | 同上 |
| `artifacts/v2_2_border_collie_exp06_resolution256_lowlr_seed2024/` | U6.1 实验权重 | 同上 |
| `artifacts/v2_2_border_collie_exp07_pair_color_jitter_lowlr_seed42/` | U6.1 实验权重 | 同上 |
| `artifacts/v2_2_border_collie_exp08_pair_sampler_lowlr_seed42/` | U6.1 实验权重 | 同上 |

**理由汇总**：①单文件 40–45 MB，12 个目录合计数百 MB，会永久污染仓库体积；
②可在需要时由 `experiment_config.json` 记录的超参复现；③任务 §2.2 与 §7 明确禁止；
④V2.1 是正式默认模型，应由发布流程管理而非源码仓库。

> 注：`artifacts/best_model.pth`（V1.1）与 `artifacts/class_names.json` 是**已跟踪**文件
> （HEAD 中已存在），本任务**未修改**它们，故不出现在 `git status` 中，也不涉及提交决策。

---

## 2. 报告 / 截图 / CSV / 隔离 runtime（`reports/`，12 项）

**明确不提交**：`reports/` 下全部内容。

| 路径 | 内容摘要 |
|---|---|
| `reports/u6_border_collie/` | 53 个文件，含 136 类逐图预测 CSV（单个约 400 KB）、混淆矩阵、实验日志 |
| `reports/u6_1_low_lr/` | 55 个文件，含 5 次实验的逐图预测与对比表 |
| `reports/u6_2_collie_pair_candidate/` | 15 个文件 + 7 张截图 + 3 个隔离 runtime 目录（含临时 SQLite） |
| `reports/u6_3_default_runtime_and_freeze/` | 21 个文件 + 4 张截图 + 3 个隔离 runtime 目录 |
| `reports/u5_5_v2_1_integration/` | 23 个文件 + 6 张截图 + 6 个隔离 runtime 目录 |
| `reports/v2_1_four_breed_candidate_implementation/` | 7 个文件（含 `acceptance_api_responses.json`） |
| `reports/v2_1_apbt_four_breed_candidate_eval/` | 评估 CSV |
| `reports/v2_1_candidate_ui_review/` | UI 审查材料 |
| `reports/v2_1_coat_pitbull_diagnostics/` | 毛色诊断 CSV |
| `reports/v2_1_diagnostics/` | 分类报告 |
| `reports/v2_1_four_breed_consistency_review/` | 一致性审查 |
| `reports/v2_1_four_breed_page_acceptance/` | 页面验收 + 截图 + runtime |

**不提交理由（按任务 §3-B 第 4 条要求，明确说明"非因无价值"）**：

1. **项目历史惯例**：`reports/` 在本仓库 git 历史中**从未被跟踪**（`git log` 无相关记录，
   当前 12 个目录全部为未跟踪项）。建议延续既有惯例，**而非因为报告内容无价值**。
2. **体积**：`u6_border_collie/` 含 2,079 行逐图预测 CSV（约 400 KB/个），
   `u6_1_low_lr/` 同类文件更多；合计数十 MB，不适合随源码提交。
3. **含隔离 runtime**：`u6_2`、`u6_3`、`u5_5` 三个报告目录内有临时 SQLite 与上传副本
   （`runtime_*/app.db`、`runtime_*/uploads/`），属运行现场，不应入库。
4. **可复现**：报告可由 `scripts/` 下的验收脚本 + 冻结的权重重新生成。

> ⚠️ **一个例外需要人工决策**：`reports/v2_1_four_breed_candidate_implementation/acceptance_api_responses.json`
> 被 `frontend/tests/predictionResultAcceptance.test.js` 读取。若"reports/ 全部不入库"，
> 该测试在新克隆环境会失败。三种处理方式见 `commit_plan.md` §3 的说明。

---

## 3. 缓存、构建产物、数据与上传——**已被 .gitignore 覆盖**

以下路径**未出现在 `git status` 中**，说明 `.gitignore` 已正确排除，无需额外处理：

| 路径 | 说明 |
|---|---|
| `.cache/` | 临时日志、冒烟产物、Playwright 安装、保护快照中间文件 |
| `frontend/dist/` | 前端构建产物 |
| `frontend/node_modules/` | 第三方依赖 |
| `.venv/` | Python 虚拟环境 |
| `data/` | 数据集（`processed`/`processed_clean`/`raw`/`v2_processed`/`v2_processed_prev`）与正式 `app.db` |
| `uploads/` | 正式上传目录（142 个文件） |

**验证结论**：U6.4 的 `git status --short` 中**无任何**上述路径，
证明忽略规则有效。**不得为了"干净状态"去修改 `.gitignore` 或删除这些目录。**

---

## 4. 验收与诊断脚本（`scripts/`，41 项）——**本次暂不提交**

**这是本任务最需要人工决策的一组。** 41 个脚本**全部为未跟踪新文件**，
可分为三类：

### 4.1 含机器本地绝对路径（**4 个，提交前必须先参数化**）

| 路径 | 硬编码内容 |
|---|---|
| `scripts/audit_v2_data_sources.py` | `cd E:\CatDogBreedNet`（L414 附近） |
| `scripts/build_clean_split.py` | `cd E:\CatDogBreedNet`（L639 附近） |
| `scripts/build_v2_dataset.py` | `cd E:\CatDogBreedNet`（L646 附近） |
| `scripts/diagnose_dataset.py` | `cd E:\CatDogBreedNet`（L852 附近） |

**不提交理由**：硬编码本机路径，在其他机器上直接运行会失败；
且它们是**数据构建脚本**，一旦误运行可能重建数据目录（高风险）。
**若未来要入库，须先改为参数化/相对路径，并加 `--dry-run` 保护。**

### 4.2 一次性验收脚本（多数）

`accept_candidate_group_api.py`、`accept_collie_pair_api.py`、
`accept_four_breed_candidate_api.py`、`accept_v2_1_integration.py`、
`check_candidate_consistency.py`、`export_candidate_triggers_val.py`、
`page_accept_*.mjs`（3 个）、`reconcile_u5_2_numbers.py`、
`validate_candidate_group_thresholds.py`、`verify_apbt_candidate_limit.py`、
`evaluate_apbt_four_group.py`、`evaluate_v2_1_subsets.py`、
`finalize_v2_1_candidate.py`、`generate_breed_mapping.py`、
`run_four_breed_backend.py`、`diagnostic_protection_snapshot.py`、
`u6_2_collie_pair_threshold.py`、`u6_baseline_val.py`、`u6_build_u6_1_reports.py`、
`u6_collect_s0.py`、`u6_collect_s0_snapshot.py`、`u6_compare_candidates.py`、
`u6_freeze_criteria.py`、`u6_parse_reviews.py`、`u6_run_experiment.py`、
`u6_warm_start_audit.py`

**暂不提交理由**：这些脚本是**针对特定任务的一次性验收/评估工具**，
尚未证明具有长期维护价值。若入库，需明确其维护责任人、补 `--help` 与参数校验。

### 4.3 可能有长期价值的少数

`scripts/u6_run_experiment.py`（实验封装，含非空目录拒绝）、
`scripts/u6_baseline_val.py`（val 单次前向派生全部指标）、
`scripts/diagnostic_protection_snapshot.py`（保护快照前后比对）、
`scripts/run_four_breed_backend.py`（隔离启动器）、
`scripts/generate_breed_mapping.py`（136 类映射生成器）

**建议**：这 5 个可作为"**候选长期工具**"单独讨论；但**本次仍不提交**，
因为任务 §4 要求"尚未证明为长期维护工具的脚本"列入暂不提交，
且它们与上述一次性脚本混在同一批未跟踪项中，**整批处理更安全**。

---

## 5. 任务单文档（`md/`，12 项）——**条件提交**

**不自动纳入**，需人工确认。理由：

1. 12 个文件**全部为未跟踪**，是否入库取决于团队对"任务单是否属于仓库内容"的约定；
2. 若团队惯例是不提交任务单，则整组排除；
3. 若决定入库，`commit_plan.md` §6 已给出完整路径与建议 message。

**本文件不代为决定**，仅在 `commit_plan.md` 中标记为"条件提交（需用户决定）"。

---

## 6. 本任务自身产生的 3 项（**同样不提交**）

U6.4 执行过程中新增了 3 个未跟踪项，**它们不属于"外部变化"**，也不建议提交：

| 路径 | 性质 |
|---|---|
| `scripts/u6_4_capture_baseline.py` | 本任务的只读基线捕获脚本（一次性） |
| `scripts/u6_4_git_review.py` | 本任务的审阅结论生成脚本（一次性） |
| `reports/u6_4_git_freeze_review/` | 本任务的报告目录（含 CSV/截图/隔离 runtime） |

**这解释了未跟踪计数从 84 → 85 → 86 的变化**（详见 `acceptance_report.md` §2）。

---

## 7. 明确不做的事

为避免"为了让状态看起来干净"而引入破坏，以下操作**明确禁止**：

- ❌ 不修改 `.gitignore` 来"隐藏"未跟踪项
- ❌ 不删除 `artifacts/`、`reports/`、`.cache/`、`data/`、`uploads/` 中的任何内容
- ❌ 不删除 U6.3 的隔离 runtime 目录（`runtime_default/`、`runtime_off/`、`runtime_web/`）
- ❌ 不 `git clean`、不 `git stash`、不 `git reset --hard`
- ❌ 不移动或重命名任何已有报告/脚本/权重
- ❌ 不为了"减少未跟踪数"而把产物塞进 `.gitignore` 或删除

> 未跟踪项多并不构成问题；**误删或误提交**才是风险。

---

## 8. 一页速查

| 想问的问题 | 答案 |
|---|---|
| `.pth` 权重能提交吗？ | **不能**（任务 §2.2 硬禁止；单个 40–45 MB） |
| `reports/` 能提交吗？ | **不建议**（历史从未跟踪 + 体积 + 含 runtime；但报告中说明这是惯例而非价值判断） |
| `scripts/` 能提交吗？ | **本次暂不提交**（一次性为主；4 个含本地绝对路径） |
| `md/` 能提交吗？ | **需人工决定**（条件提交） |
| `.cache/`、`data/`、`uploads/` 呢？ | 已被 `.gitignore` 覆盖，**无需处理** |
| 本任务新增的 3 项呢？ | **不提交** |
| 需要清理工作区吗？ | **不需要，也不允许** |
