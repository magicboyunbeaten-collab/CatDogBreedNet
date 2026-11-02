# U6.4.1：测试修复与 Git 正式固化 — 验收报告

> **任务结论：完成。** 两项测试修复已落地，三项必要测试在**任何 Git 写操作之前**全部通过，
> A/B/C/D 四组以精确路径提交成功（4 个可核对 commit），提交后完整回归全绿，
> 模型/数据/数据库/上传保护核验全部一致。
>
> 起始 HEAD：`547c55dd96b5d2a9aca71c58458f4192e55b38f5`（`547c55d`）
> 结束 HEAD：**`ca86b0b`**
> 分支：`master`（**未推远端**）
> 生成时间：2026-10-21

---

## 0. 一页结论

| 项目 | 结果 |
|---|---|
| 两项测试修复 | ✅ 完成，业务算法**零改动** |
| 提交前三项测试 | ✅ `pytest` 268 passed / `npm test` 85 passed / `build` 1.70s，**全部退出码 0** |
| 四个提交 | ✅ `52165ca`(A,10) → `bfb9fd0`(B,9) → `62c86bf`(C,2) → `ca86b0b`(D,4) |
| 提交后完整回归 | ✅ 268 passed / 85 passed / build 816ms，全部退出码 0 |
| 保护核验 | ✅ 全部一致（V1.1/V2.1 哈希、五数据目录、DB 142 条 ok、uploads 142） |
| 剩余未跟踪 | **82 个状态条目 / 457 个文件**（本次报告目录与清点脚本另计），全部登记为**有意排除** |
| 已跟踪修改遗留 | **0**（`git status --short` 中 `M` 数为 0） |
| 训练 / test split / 正式 DB 写入 | **各 0 次** |

---

## 1. 开工状态核验（§1.3）

### 1.1 基线可解释性（关键）

| 项目 | 实测 |
|---|---|
| HEAD | `547c55dd96b5d2a9aca71c58458f4192e55b38f5` —— **与 U6.4 基线一致** |
| 分支 | `master` |
| `git status --short` | **18 个已跟踪修改 + 89 个未跟踪条目** |
| `git diff --cached --stat` | **空** |

**未跟踪项数量的完整解释（逐项验证，不是估算）**：

| 时点 | 未跟踪条目 | 变化来源 |
|---|---:|---|
| U6.4 结束时（`file_by_file_review.csv` 中 `tracked=no` 行数） | **87** | — |
| U6.4.1 开工时 | **88** | **+1 = `md/U6.4.1_测试修复与Git正式固化执行.md`**（本任务单） |
| 创建本任务报告目录后 | **89** | +1 = `reports/u6_4_1_git_finalization/` |

→ **不存在无法解释的外部代码改动。** 已如实记录而非假定。

### 1.2 已跟踪修改清单（18 项，全部为 A/B/C/D 组目标）

按 `--name-status` 输出，18 项全部落在 A/B/C/D 四组内，
其中 7 项为未跟踪新文件（`candidate_group.py`、`u6_pair_training.py`、
`predictionResult.test.js`、`predictionResultAcceptance.test.js`、
`colliePairCandidate.test.js`、`test_candidate_group.py`、`test_collie_pair_candidate.py`），
**18 + 7 = 25，与 A/B/C/D 清单完全吻合**。

### 1.3 快照文件

| 文件 | 内容 |
|---|---|
| `git_status_before.txt` | `git status --short` 全文 |
| `git_diff_stat_before.txt` | `git diff --stat` 全文 |
| `git_diff_name_status_before.txt` | `git diff --name-status` 全文 |
| `protection_snapshot_before.json` | V1.1/V2.1 哈希、五数据目录、DB、uploads、git 状态 |

---

## 2. 两项必要修复（§2）

### 2.1 `frontend/tests/predictionResultAcceptance.test.js` 自包含化

**问题**：原文件在模块顶层

```js
const evidence = JSON.parse(readFileSync(
  resolve(here, '../../reports/v2_1_four_breed_candidate_implementation/acceptance_api_responses.json'),
  'utf-8'))
```

`reports/` 在本仓库从未被跟踪，干净克隆里该测试必然失败。

**修复**：从真实 JSON 中**原样提取**四段响应作为 inline fixture：

| 常量 | 来源图片（validation 相对路径） | 作用 |
|---|---|---|
| `TRIGGERED_APBT` | `american_pit_bull_terrier/american_pit_bull_terrier_132.jpg` | Top-1 = APBT 的触发 |
| `TRIGGERED_AMSTAFF` | `american_staffordshire_terrier/n02093428_8135.jpg` | Top-1 = AmStaff 的触发 |
| `CONTROL_NOT_TRIGGERED` | `Abyssinian/Abyssinian_10.jpg` | Top-1 在组外 → `triggered=false` |
| `SWITCH_OFF` | 同上首图（关闭总开关） | `candidate_group=null` |

**验收证据**：

| 检查项 | 结果 |
|---|---|
| `import { readFileSync } from 'node:fs'` | **已删除** |
| `node:url` / `node:path` | **已删除** |
| 顶层 `readFileSync(...)` | **已删除** |
| 全仓搜索 `acceptance_api_responses` | **仅出现在文件头注释**（说明改造原因），无运行时引用 |
| 全仓搜索 `readFileSync(` / `from 'node:` / `require('fs')` | **0 命中** |
| 8 个场景 A–H | **全部保留**（名称、顺序、断言逐条不变） |
| 断言精度 | **未放宽**：`toBeCloseTo(100, 2)`、`toBeCloseTo(expected, 2)`、`toBeCloseTo(..., 9)` 原样 |
| `PredictionResult.vue` | **零改动**（未为迁就测试改组件） |
| 测试结果 | **8 passed** |

**数值保真**：`group_score` / `group_mass` / `group_margin` 逐字段复制，未做任何四舍五入或"美化"。
两条触发样本的组内得分和分别为 `100.0` 与 `99.99999999999999`（浮点累加），均满足断言。

**fixture 刻意不含 `group_id`**：`group_id` 是 U6.2 才加入的字段，被引用的那份真实响应本就没有。
保持原样既忠实于历史响应，也顺带覆盖「U6.2 之前旧响应」的向后兼容路径。

### 2.2 「同类别数但名称/顺序不同」回归测试

**新增三个用例**（`tests/test_predictor_service.py`）：

| 用例 | 构造 | 断言要点 |
|---|---|---|
| `test_same_class_count_but_reordered_names_refuses_to_start` | `["chihuahua","boxer","beagle"]`（同集合顺序反转） | `class mapping mismatch at index 0`；`checkpoint='beagle'`；`dataset='chihuahua'`；**不含** `class count mismatch` |
| `test_same_class_count_but_different_name_refuses_to_start` | `["beagle","boxer","pug"]`（仅 index 2 不同） | `at index 2`；`checkpoint='chihuahua'`；`dataset='pug'`；**不含** `at index 0` / `at index 1` / `class count mismatch` |
| `test_same_class_count_mismatch_does_not_start_service` | 顺序反转 | 异常抛出后 `service is None`（无静默回退、无自动重排） |

**验收证据**：

| 检查项 | 结果 |
|---|---|
| 使用临时目录与假权重 | ✅ 全部在 `tmp_path` 内，配合既有 `fake_predictor` fixture |
| 不触碰真实权重/正式数据 | ✅ |
| 保留索引级错误信息 | ✅ 断言索引号 + 两侧真实标签 |
| 不落入「数量」分支 | ✅ 显式断言 `"class count mismatch" not in message` |
| **未修改 `backend/app/services/predictor.py`** | ✅ 零改动 |
| **未修改 `ml/model.py`** | ✅ 零改动 |
| 测试文件单跑 | **14 passed**（11 既有 + 3 新增） |

**为什么现有用例不够**：`test_mismatched_class_names_refuses_to_start` 虽用 `["beagle","boxer","pug"]`
覆盖了"同数量名称不同"，但①未断言索引位置与两侧名称 ②未覆盖"同集合顺序反转"
③未断言不落入数量分支。三个新用例正好补齐这三处盲点，且不重复。

---

## 3. 三项测试硬门禁（§3）

**顺序保证**：三项测试全部在**第一次 `git add` 之前**完成（见 `test_results_precommit.md`）。

| # | 命令 | 退出码 | 结果 |
|---:|---|---:|---|
| 1 | `.venv\Scripts\python.exe -m pytest tests/ -q` | **0** | **268 passed** |
| 2 | `npm test` | **0** | **85 passed / 12 files** |
| 3 | `npm run build` | **0** | **成功 1.70s** |

全绿后才进入 §4。**未出现**"改第 2 节以外的生产代码才能通过"的情形。

---

## 4. 四组提交（§4）

详见 `commits.md`。摘要：

| 组 | commit | message | 文件数 | +/− |
|---|---|---|---:|---:|
| A | `52165ca` | Integrate V2.1 136-class prediction and candidate groups | 10 | +942/−23 |
| B | `bfb9fd0` | Add regression tests for prediction and candidate UX | 9 | +2136/−19 |
| C | `62c86bf` | Use V2.1 defaults in Windows launchers | 2 | +40/−11 |
| D | `ca86b0b` | Extend training infrastructure for warm-start and pair experiments | 4 | +632/−26 |
| | | **合计** | **25** | **+3750/−79** |

**每组均执行**：`git add -- <显式路径>`（无 `.`/`-A`/通配符）→ `--name-status` 集合相等校验
（四组均为"多出 0 / 缺少 0"）→ 三条安全判据 → `git commit` → `git log -1` / `git show --stat` 记录
→ 组后相关测试。

### 4.1 A 组初筛误报的处理（如实记录）

首轮用朴素关键字扫描暂存 diff 时命中 `artifacts/`(2) 与 `reports/`(5)。逐行检查确认
**全部是注释/文档中的路径引用**，例如：

```
#: 需要回退时用环境变量指向它们即可（见 reports/u5_5_v2_1_integration/rollback.md）。
* 键**完全等于** `artifacts/v2_1_136classes_seed42/class_names.json` 中的
```

**没有任何来自这两个目录的文件被暂存**。因此改为三条**按路径判定**的精确判据：

1. 暂存路径是否落在 `artifacts|reports|data|uploads|.cache|dist|md`
2. 新增行是否含 `E:\` / `E:/` / `C:\Users`
3. 新增行是否含密钥特征

四组全部通过。

### 4.2 B 组的一次提交失败（如实记录）

首次用 PowerShell here-string 传多行 message，PowerShell 把消息中一段（含 `without`）
当作 pathspec，git 报 `error: pathspec 'without' did not match any file(s) known to git`，
**提交未发生**（HEAD 仍 `52165ca`，暂存区仍恰为 9 项，工作区未受损）。
随后改用 `git commit -F .cache/u641_B_msg.txt` 成功。C、D 组同样用 `-F`。

### 4.3 D 组的三类来源披露

`ml/train.py` 混合三类来源，commit body **完整披露**而非只写标题：

1. **U6-C**：`--pair-color-jitter` / `--pair-sampler-weight` / `--image-size` + `ml/u6_pair_training.py`
2. **U6 warm-start 修复**：原先无条件跳过分类头，导致 136→136 也把 `fc.*` 置随机；
   现改为类别名与顺序完全一致时连 `fc.*` 一起继承并记录 `head_transferred`
3. **U4 训练扩展**：`--init-from` / `--monitor` / `--lr-head` / `--lr-backbone` 等（本次首次入库）

并注明"本提交只涉及训练工具，线上推理路径不变"。

---

## 5. 提交后完整回归与保护核验（§5）

详见 `test_results_postcommit.md`。

| 检查项 | 结果 |
|---|---|
| `pytest tests/ -q` | **268 passed**，退出码 0 |
| `npm test` | **85 passed / 12 files**，退出码 0 |
| `npm run build` | **成功 816ms**，退出码 0 |
| `git log -4 --oneline` | **恰好 4 个有序提交** A→B→C→D ✅ |
| `git diff --cached --stat` | **空** ✅ |
| V1.1 权重哈希 | `89ef468f…a256` —— **未变** |
| V2.1 四文件 | **未变** |
| 五个数据目录 | 文件数与字节 **未变** |
| 正式 `data/app.db` | **142 条**，`integrity: ok` —— **未变，写入 0 次** |
| 项目 `uploads/` | **142 文件** —— **未变，写入 0 次** |
| 默认 `weights_path` | V2.1 目录 —— **未变** |
| 默认 `class_names_path` | V2.1 目录 —— **未变** |
| `candidate_group_enabled` | **True** —— **未变** |
| 训练 | **0 次** |
| test split 访问 | **0 次** |

---

## 6. 有意排除的剩余内容（§6）

清单文件：`remaining_worktree_inventory.csv`（**458 行，逐文件**，`intentional=yes` 全部）。
**未删除任何一项，未修改 `.gitignore`，未隐藏任何文件。**

### 6.1 三个口径的差异（必须说清，否则会误读）

| 口径 | 数量 | 说明 |
|---|---:|---|
| `git status --short` 中 `??` 条目 | **83** | git 把未跟踪**目录**折叠为 1 条 |
| `git ls-files --others --exclude-standard` | **458** | 逐**文件**展开（本清单采用此口径） |
| 其中被 `.gitignore` 排除（不出现在上面两处） | 331 条目 | 含 **100 个 `.pth`，共 4.45 GB**；`.cache/`（19.4 GB）、`data/`（7.5 GB）、`uploads/`（14 MB）等 |

> **关键事实**：`.gitignore` 已包含 `artifacts/*.pth` 与 `artifacts/**/*.pth`，
> 因此 **100 个权重文件（4.45 GB）从来不会出现在 `git status` 里**，也就不存在被误提交的风险。
> 本清单的字节总数（36.8 MB）**不含**这些被忽略的权重与数据——如不加说明会被严重误读。

### 6.2 按类型统计（清单口径，458 行）

| 类型 | 行数 | 文件数 | 体积 | 排除理由 |
|---|---:|---:|---:|---|
| `acceptance_reports_and_runtime`（`reports/`） | 358 | 358 | 33.59 MB | 验收报告/CSV/截图/临时 SQLite 与 uploads 副本。**项目历史从未跟踪 `reports/`，延续既有惯例——这是惯例决定，不是"内容无价值"** |
| `model_weights_and_experiments`（`artifacts/`） | 43 | 43 | 2.50 MB | 实验配置/日志/指标等非 `.pth` 产物；`.pth` 已被 gitignore 排除 |
| `one_off_scripts`（`scripts/`） | 44 | 44 | 0.54 MB | 一次性验收/诊断/实验脚本，尚未证明为长期维护工具；其中 4 个还含机器本地绝对路径（`audit_v2_data_sources.py`、`build_clean_split.py`、`build_v2_dataset.py`、`diagnose_dataset.py`） |
| `task_sheets`（`md/`） | 13 | 13 | 0.16 MB | 任务单文档；项目未将 `md/` 纳入版本控制，是否入库待人工决定 |
| **合计** | **458** | **458** | **36.8 MB** | 全部 `intentional=yes` |

### 6.3 磁盘实际体积对照（供审查者理解规模）

| 目录 | 文件数 | 磁盘体积 | 是否被 gitignore |
|---|---:|---:|---|
| `artifacts/` | 223 | **4,453.5 MB** | `.pth` 被忽略（100 个 / 4,451 MB） |
| `reports/` | 1,069 | 72.6 MB | 部分 CSV/PNG 被忽略 |
| `data/` | 114,385 | **7,491.8 MB** | 全部被忽略 |
| `uploads/` | 142 | 14.0 MB | 全部被忽略 |
| `.cache/` | 26,279 | **19,375.8 MB** | 全部被忽略 |
| `frontend/dist/` | 3 | 2.5 MB | 被忽略 |

### 6.4 本任务自身新增（同样不提交）

| 路径 | 说明 |
|---|---|
| `reports/u6_4_1_git_finalization/` | 本任务报告目录（已含在 `reports/` 的 358 行内） |
| `scripts/u6_4_1_remaining_inventory.py` | 本任务的清单生成脚本（已含在 `scripts/` 的 44 行内） |

---

## 7. 完成标准逐项核对（§8）

| # | 标准 | 结果 | 证据 |
|---:|---|---|---|
| 1 | 两项测试改进完成，业务算法未被擅自改变 | ✅ | `PredictionResult.vue`、`predictor.py`、`ml/model.py` 本轮**零改动** |
| 2 | **任何 Git 写操作之前**三项测试全通过 | ✅ | `test_results_precommit.md`；第一次 `git add` 晚于三项全绿 |
| 3 | A/B/C/D 使用精确路径完成提交，不含清单外文件 | ✅ | 四组 `--name-status` 集合相等，多出 0 / 缺少 0 |
| 4 | 每个 commit 可用 `git show --stat` 核对，未推远端 | ✅ | `commits.md` 逐组贴出 `show --stat`；**未执行任何 push** |
| 5 | 提交后完整回归全部通过 | ✅ | 268 / 85 / build 816ms，退出码全 0 |
| 6 | 模型/数据/数据库/上传保护核验全通过 | ✅ | 快照前后自动比对一致；DB 142 ok；uploads 142 |
| 7 | 剩余未跟踪内容有清晰有意排除清单 | ✅ | `remaining_worktree_inventory.csv`（458 行，`intentional=yes`） |
| 8 | 未训练、未访问 test split、未执行清理/破坏性 Git 命令 | ✅ | 训练 0 次、test 访问 0 次、无 reset/clean/checkout/stash/rebase/amend/push |

**"彻底解决"口径的达成情况**：

- ✅ 已审核的长期生产功能（A）、配套测试（B）、启动入口（C）、训练基础设施（D）
  全部形成可追溯 commit
- ✅ 工作区中**已跟踪修改 `M` 数量 = 0** —— 这四组不再遗留任何未提交代码
- ✅ 审计报告、一次性脚本、实验产物、任务单依仓库惯例**明确排除**，并在清单中逐项登记，
  **未把它们误报为待提交源代码，也未删除或隐藏**

---

## 8. 交付物清单（`reports/u6_4_1_git_finalization/`）

| 文件 | 内容 |
|---|---|
| `acceptance_report.md` | 本报告 |
| `test_results_precommit.md` | 提交前三项测试的命令、退出码、输出摘要、两项修复的验收证据 |
| `test_results_postcommit.md` | 提交后完整回归 + Git 状态 + 保护核验 |
| `commits.md` | A/B/C/D 每个 commit 的 hash、message、完整文件路径、核对记录与两次失败/误报的如实说明 |
| `remaining_worktree_inventory.csv` | **458 行**逐文件登记（path / type / runtime_required / file_count / total_bytes / reason_excluded / intentional） |
| `protection_snapshot_before.json` / `_after.json` | 保护快照（自动比对一致） |
| `git_status_before.txt` / `git_status_after.txt` / `git_log_after.txt` | Git 原文快照 |
| `git_diff_stat_before.txt` / `git_diff_name_status_before.txt` | 开工差异原文 |

**未覆盖**：`reports/u6_4_git_freeze_review/`、`reports/u6_3_default_runtime_and_freeze/`
及更早的任何报告（均为只读引用）。

---

## 9. 需要人工知悉的三点

1. **`reports/` 与 `scripts/` 仍为未跟踪**：这是**依仓库既有惯例的有意排除**，不是遗漏。
   若团队希望把 `reports/` 或其中某几个长期工具脚本入库，需单独决定（并注意
   `reports/` 下有 358 个文件、部分 CSV 已被 `.gitignore` 忽略，需先调整忽略规则）。
2. **`md/` 13 个任务单未入库**：是否入库取决于团队对"任务单是否属于仓库内容"的约定，
   本任务未代为决定。
3. **`scripts/` 中 4 个脚本含机器本地绝对路径**（`E:\CatDogBreedNet`）：
   若未来要入库，须先改为参数化或相对路径，并加 `--dry-run` 保护。

---

**U6.4.1 完成。四个提交已固化，测试与保护证据齐备，剩余内容全部登记为有意排除。未推送远端。**
