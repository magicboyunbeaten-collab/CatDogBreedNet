# U6.5：远端同步核验与阶段收尾 — 验收报告

> **结论：阶段验收通过。** U6.4.1 的四个提交已确认同步到远端（`git ls-remote` 实测），
> 工作区无已跟踪修改、暂存区为空；默认配置实测加载 V2.1（136 类），
> 两套候选策略各按预期触发/不触发；11 项保护核验全部一致。
>
> 本地 HEAD：**`ca86b0b7bdbb1530f1c96896c3316e48a81f9868`**
> 远端 `refs/heads/master`：**`ca86b0b7bdbb1530f1c96896c3316e48a81f9868`**
> 生成时间：2026-10-21

---

## 0. 关于"远端已同步"这条结论的取证方式（必读）

> **远端 SHA 是通过 `git ls-remote origin refs/heads/master` 实际读取的**，
> 命令退出码 `LS_REMOTE_EXIT=0`，返回 `ca86b0b7bdbb1530f1c96896c3316e48a81f9868	refs/heads/master`。
> **不是**凭用户陈述，也**不是**凭本地 `origin/master` tracking ref（该 ref 可能因未 fetch 而过期）。
> 本地 tracking ref 仅在 `git_sync_evidence.txt` §9 作为**附带对照**列出，并已标注"不作判据"。
>
> **补充说明（如实记录一次失败）**：阶段 A 判据处的首次读取**成功**（`exit 0`，上述 SHA 即其返回值）。
> 收尾复核时**再次**执行 `git ls-remote` 却遇到网络瞬时故障：
> `error: RPC failed; curl 28 Failed to connect to github.com:443 after 21067 ms`、
> `fatal: expected flush after ref listing`（退出码非 0，无输出）。
> **该失败不影响本结论**——结论依据是首次成功读取的原始输出（已固化在 `git_sync_evidence.txt` §7），
> 而不是这次失败的重试；且本任务全程未执行 `fetch`/`pull`/`push`，远端不可能因本任务而变化。

U6.4.1 报告生成时记录"未推送远端"，那**是当时的快照**；本任务重新读取远端，结论已更新为"已同步"。
本次核验未执行任何 `fetch` / `pull` / `push`。

---

## 1. 阶段 A：远端同步核验

完整命令原文见 `git_sync_evidence.txt`。摘要：

| # | 命令 | 结果 |
|---|---|---|
| 1 | `git rev-parse HEAD` | `ca86b0b7bdbb1530f1c96896c3316e48a81f9868` |
| 2 | `git branch --show-current` | `master` |
| 3 | `git log -4 --oneline` | `ca86b0b` → `62c86bf` → `bfb9fd0` → `52165ca` |
| 4 | `git status --short` | 0 个 `M`，84 个 `??`（均为有意保留项，见 §5） |
| 5 | `git diff --cached --name-status` | **空** |
| 6 | `git diff --name-status` | **空** |
| 7 | **`git ls-remote origin refs/heads/master`** | **`ca86b0b7bdbb1530f1c96896c3316e48a81f9868`**，exit 0 |

### 1.1 四条判据（全部满足）

| # | 判据 | 结果 |
|---|---|---|
| 1 | HEAD == `ca86b0b7bdbb1530f1c96896c3316e48a81f9868` | **PASS** |
| 2 | 远端 SHA 与本地 HEAD **逐字符相同** | **PASS** |
| 3 | `git diff --cached --name-status` 为空 | **PASS** |
| 4 | `git status --short` 中 `M`（已跟踪未暂存修改）为 0 | **PASS**（实际 0） |

### 1.2 "四个提交都在远端"的证明链

远端 SHA == 本地 HEAD，且四个提交均为 HEAD 的祖先 →
四个提交均可达自远端 `refs/heads/master`。

| 提交 | message | `merge-base --is-ancestor <c> HEAD` |
|---|---|---|
| `52165ca` | Integrate V2.1 136-class prediction and candidate groups | **True** |
| `bfb9fd0` | Add regression tests for prediction and candidate UX | **True** |
| `62c86bf` | Use V2.1 defaults in Windows launchers | **True** |
| `ca86b0b` | Extend training infrastructure for warm-start and pair experiments | **True** |

> 该证明不依赖任何 `fetch`：`git ls-remote` 给出远端分支的确切 SHA，
> `merge-base --is-ancestor` 在本地对象库中判定可达性，两者结合即可确认四个提交已在远端。

---

## 2. 阶段 B：默认启动冒烟测试

### 2.1 环境构造（关键：验证的是**默认配置**）

| 项目 | 值 |
|---|---|
| 启动方式 | `python -m uvicorn backend.app.main:app --port 8000`（与 `启动后端.bat` 的最终命令一致） |
| `CATDOG_DB_PATH` | `reports/u6_5_remote_sync_wrapup/runtime/app.db`（**隔离**） |
| `CATDOG_UPLOAD_DIR` | `reports/u6_5_remote_sync_wrapup/runtime/uploads`（**隔离**） |
| `CATDOG_WEIGHTS_PATH` | **未设置** |
| `CATDOG_CLASS_NAMES_PATH` | **未设置** |
| `CATDOG_CANDIDATE_GROUP_ENABLED` | **未设置** |

→ 因为三个关键变量**都未设置**，模型路径与候选开关全部走 `config.py` 的类默认值，
**验证的是日常默认配置本身**，而不是被覆盖的配置。仅"存储位置"被重定向到隔离目录。

### 2.2 `/api/health` 实测

```json
{
  "status": "ok",
  "model_loaded": true,
  "num_classes": 136,
  "model_weights": "best_model.pth",
  "model_error": null,
  "version": "1.0.0"
}
```

| 要求 | 实测 | 结果 |
|---|---|---|
| `num_classes == 136` | 136 | **PASS** |
| `model_loaded == true` | true | **PASS** |
| `model_error == null` | null | **PASS** |

### 2.3 模型版本证据（三源交叉，不只靠文件名）

> ⚠️ **`model_weights` 只返回文件名 `best_model.pth`，而 V1.1 与 V2.1 的权重同名**，
> 因此**文件名本身不足以判定版本**。本报告用三条独立证据交叉确认：

| # | 证据 | 值 |
|---|---|---|
| 1 | `/api/health.num_classes` | **136**（V1.1 为 37） |
| 2 | 启动日志 | **`model ready: version=v2_1_136classes_candidate arch=resnet18 classes=136 device=cuda (weights: best_model.pth)`** |
| 3 | V2.1 checkpoint SHA256 | `423e218a29230f8248e071e7fb47b88afb2c1f2b67fb860224f6f319041821e1`（与 §4 期望值一致） |

启动日志另含：`class mapping verified against class_names.json (136 classes)`、
`database ready: app.db`（确认写入的是隔离 DB）。

### 2.4 候选开关有效值

`config.py` 默认 `candidate_group_enabled = True`，本次**未设置任何覆盖变量**，
且实测两套策略均按预期触发 → 有效值为 **True**。

### 2.5 三张 validation 样本（全部 PASS）

| 用途 | 样本 | Top-1（原始） | 候选组 ID | 触发 | 组内得分和 |
|---|---|---|---|---:|---:|
| collie-pair 触发 | `border_collie/n02106166_416.jpg` | `border_collie` 0.600428 | `collie-pair` | **True** | **100.0** |
| four-breed 触发 | `american_pit_bull_terrier/american_pit_bull_terrier_132.jpg` | `american_pit_bull_terrier` 0.467221 | `four-breed-bully` | **True** | **100.0** |
| 非目标对照 | `beagle/beagle_101.jpg` | `beagle` 0.986948 | `four-breed-bully` | **False** | —（不触发，不计算） |

**collie-pair 候选（`val-2026-10-21-collie-pair-v1`，mass 0.999177 / margin 0.201679）**：

| 候选 | 原始概率 | 组内相对得分 |
|---|---:|---:|
| 边境牧羊犬（border_collie） | 0.600428 | **60.0923%** |
| 柯利牧羊犬（collie） | 0.398749 | **39.9077%** |

**four-breed-bully 候选（`val-2026-10-19-four-breed-b1`，mass 0.857883 / margin 0.076616）**：

| 候选 | 原始概率 | 组内相对得分 |
|---|---:|---:|
| 美国比特斗牛梗 | 0.467221 | **54.4621%** |
| 美国斯塔福郡梗 | 0.390605 | **45.5313%** |
| 斯塔福郡斗牛梗 | 0.000039 | **0.0045%** |
| 美国斗牛犬 | 0.000018 | **0.0021%** |

**非目标对照**：`triggered=False`，前端因此不渲染候选区（`candidate_group` 仍返回对象，
这是既有行为，非缺陷）。

### 2.6 逐样本断言结果（9 项 × 3 张）

| 断言 | collie-pair | four-breed | 对照 |
|---|:--:|:--:|:--:|
| HTTP 200 | PASS | PASS | PASS |
| **原始 Top-1 标签未被替换**（`group.top1_breed == predictions[0].breed`） | PASS | PASS | PASS |
| **原始 Top-1 分数未被替换** | PASS | PASS | PASS |
| Top-K 仍为 3 行 | PASS | PASS | PASS |
| 响应**不含** `probabilities` 字段 | PASS | PASS | PASS |
| 触发状态符合预期 | PASS | PASS | PASS |
| 候选组 ID 符合预期 | PASS | PASS | PASS |
| 未误入另一套策略（对照组 ≠ `collie-pair`） | — | — | PASS |
| 组内得分和 ≈ 100（容差 1e-3） | PASS | PASS | n/a |
| 得分严格等于 `original / group_mass × 100` | PASS | PASS | n/a |

**结论：候选提示只追加"候选区"信息，原始 Top-1、Top-K 与分数均未被替换。**
组内得分明确为"候选组内相对得分"，不是整体识别置信度。

### 2.7 进程与隔离存储

| 项目 | 结果 |
|---|---|
| 服务进程 | **已停止**，端口 8000 **已释放** |
| 隔离 DB | `reports/u6_5_remote_sync_wrapup/runtime/app.db`（8,192 B） |
| 隔离 uploads | 6 个文件（2 轮 × 3 样本；第一轮因断言笔误重跑，见 §6） |
| 临时目录 | **按任务要求保留作审计证据，未清理** |

---

## 3. 是否重跑完整测试（任务 §4）

**未重跑**，引用 U6.4.1 实测证据。依据三条，全部成立：

1. 当前 HEAD **精确等于** `ca86b0b7bdbb1530f1c96896c3316e48a81f9868`；
2. **远端 SHA 与本地相同**（`git ls-remote` 实测）；
3. `git status --short` 中 `M` = **0**，本任务**零代码改动**（只读核验 + 隔离冒烟）。

引用的 U6.4.1 结果（`reports/u6_4_1_git_finalization/test_results_precommit.md` 与 `test_results_postcommit.md`）：

| 命令 | 结果 |
|---|---|
| `pytest tests/ -q` | **268 passed** |
| `npm test` | **85 passed / 12 files** |
| `npm run build` | **成功**（816 ms） |

> 若人工要求在当前版本上重跑，命令同上；本报告不将旧结果声称为"本次新跑的验证"，
> 仅声明"HEAD 与远端一致且无代码改动，故该结果适用于当前版本"。

---

## 4. 保护核验（11/11 通过）

详见 `protection_summary.json`。核验方式为**只读**（`hashlib` / `sqlite3` SELECT / `pathlib` stat），
**未执行任何可能改写正式 SQLite 或 uploads 的操作**。

| # | 检查项 | 实测 | 结果 |
|---:|---|---|---|
| 1 | V1.1 `artifacts/best_model.pth` SHA256 | `89ef468f…b1a256` | **PASS**（与期望逐字符一致） |
| 2 | V2.1 `best_model.pth` SHA256 | `423e218a…821e1` | **PASS** |
| 3 | V2.1 `class_names.json` | `216dae77…a07505ad` | **PASS**（可读、64 位） |
| 4 | V2.1 `model_version.json` | `0b0e5c7f…fb1cdd08` | **PASS** |
| 5 | V2.1 `experiment_config.json` | `0253416b…4e4f2439a` | **PASS** |
| 6 | 五个数据目录 | 见下表 | **PASS**（均存在、只读统计） |
| 7 | 正式 `data/app.db` 记录数 | **142** | **PASS** |
| 8 | 正式 `data/app.db` `integrity_check` | **ok** | **PASS** |
| 9 | 项目 `uploads/` 文件数 | **142** | **PASS** |
| 10 | 默认 `weights_path` / `class_names_path` | 均指向 `v2_1_136classes_seed42/` | **PASS** |
| 11 | 默认 `candidate_group_enabled` | **True** | **PASS** |

**五个数据目录（只读文件数 / 字节）**：

| 目录 | 文件数 | 字节 |
|---|---:|---:|
| `data/processed` | 7,349 | 790,860,970 |
| `data/processed_clean` | 7,325 | 787,775,992 |
| `data/raw` | 25,867 | 1,632,137,687 |
| `data/v2_processed` | 24,098 | 1,428,084,982 |
| `data/v2_processed_prev` | 29,158 | 1,622,680,409 |

**正式 DB 与 uploads 零写入**：本次所有上传均写入
`reports/u6_5_remote_sync_wrapup/runtime/uploads/`（6 个文件），
正式 `data/app.db` 仍 142 条、`uploads/` 仍 142 文件。

---

## 5. 工作区状态与"有意保留的未跟踪项"

| 项目 | 数量 | 说明 |
|---|---:|---|
| 已跟踪修改（`M`） | **0** | 无遗留、无暂存内容 |
| 暂存区 | **空** | — |
| 未跟踪条目（`??`） | **85**（收尾时）/ **84**（阶段 A 判据时） | 见下方分解 |

**未跟踪条目的完整分解（逐项，不是估算）**：

| 时点 | `??` 条目 | 变化来源 |
|---|---:|---|
| U6.4.1 结束时（`remaining_worktree_inventory.csv`） | 83 | — |
| U6.5 阶段 A 判据时 | **84** | **+1 = `md/U6.5_远端同步核验与阶段收尾_修订版.md`**（本任务单） |
| U6.5 收尾时 | **85** | **+1 = `reports/u6_5_remote_sync_wrapup/`**（本任务报告目录） |

> 另有一个**对 git 不可见**的目录 `reports/u6_5_remote_sync_wrapup+/`（见 §6.2）：
> 它唯一的文件是 `runtime/app.db`，被 `.gitignore:28` 的 `*.db` 规则忽略，
> 因此**不会出现在 `git status` 中**，也不计入上面 85 项。

**为何 84 个 `??` 不是"提交遗漏"**：U6.4.1 已在
`reports/u6_4_1_git_finalization/remaining_worktree_inventory.csv`
逐文件登记 458 项为 `intentional=yes`，分类为：

| 类型 | 说明 |
|---|---|
| `reports/` | 验收报告、CSV、截图、隔离 runtime 副本 —— 项目历史从未跟踪，延续惯例 |
| `scripts/` | 一次性验收/诊断/实验脚本（其中 4 个含机器本地绝对路径） |
| `artifacts/` | 实验配置/日志/指标（`.pth` 已被 `.gitignore` 排除，4.45 GB 从不出现） |
| `md/` | 任务单文档，是否入库待人工决定 |

→ **没有未解释的新增文件。** 工作区**不需要**为了"干净"而清理。

**本任务新增（同样为有意保留，不提交）**：

| 路径 | 说明 |
|---|---|
| `reports/u6_5_remote_sync_wrapup/` | 本任务报告目录 |
| `reports/u6_5_remote_sync_wrapup+/` | **⚠ 见 §6 第 2 条**，为本任务一次命令路径拼接错误产生的空壳目录 |

---

## 6. 两处需要如实说明的过程问题

### 6.1 冒烟脚本第一轮断言写错（非产品缺陷）

第一轮断言把"非目标对照"的期望写成 `group_id is None`，实际返回
`group_id="four-breed-bully"` + `triggered=False`。

**这是既有设计行为**：Top-1 在两组之外时，四类策略仍返回一个 `triggered=False` 的字典，
前端只在 `triggered === true` 时渲染候选区。U6.3/U6.4 的报告中已记录同一行为
（"对组外图片，API 仍返回 candidate_group 对象但 triggered=False"）。

修正断言为"`triggered=False` 且未误入 `collie-pair` 分支"后重跑，三张样本全部 PASS。
**产品代码未做任何修改。**
副作用：隔离 uploads 因此有 6 个文件（2 轮 × 3 张），已在 §2.7 记录。

### 6.2 一个由命令拼接错误产生的多余目录

首次启动隔离实例时，PowerShell 把 `$d+"\runtime"` 拼成了带字面 `+` 的路径，
意外创建了 `reports/u6_5_remote_sync_wrapup+/runtime/app.db`（8,192 B，空 schema）。

按任务"不删除或移动 runtime 目录"的要求，**未删除**，保留待人工处理。
它**不包含任何历史证据**，仅是本任务一次命令笔误的产物，可安全删除。
第二次启动改用正确路径 `reports/u6_5_remote_sync_wrapup/runtime`，冒烟证据均来自后者。

**为何它在 `git status` 里看不见**：该目录唯一的文件 `runtime/app.db` 被
`.gitignore:28` 的 `*.db` 规则匹配（`git check-ignore -v` 实测输出：
`.gitignore:28:*.db	reports/u6_5_remote_sync_wrapup+/runtime/app.db`），
因此 git 认为该目录下没有"未跟踪的非忽略文件"，不会把它列为 `??`。
这不是被隐藏，而是既有的忽略规则使然——**记录在此以免读者以为工作区只有 85 项未跟踪**。

### 6.3 启动日志级别的一处调整说明

`scripts/run_four_breed_backend.py` 内置 `log_level="warning"`，会抑制
`INFO: model ready: version=...` 这一行——而任务要求必须从启动日志取版本证据。
因此改用与 `启动后端.bat` 最终命令等价的
`python -m uvicorn backend.app.main:app --port 8000`（默认 info 级别），
以便捕获该行。**未修改任何脚本**，仅改变了启动方式。

---

## 7. 逐条回答任务 §8 的 8 个问题

**① 本地 HEAD 是否等于预期 `ca86b0b`？**
**是。** `git rev-parse HEAD` = `ca86b0b7bdbb1530f1c96896c3316e48a81f9868`，短 SHA `ca86b0b`。

**② 远端 `refs/heads/master` 的实际 SHA 是什么？是否与本地完全一致？**
**`ca86b0b7bdbb1530f1c96896c3316e48a81f9868`，与本地逐字符完全一致。**
该值由 **`git ls-remote origin refs/heads/master` 实际读取**（退出码 0），非本地缓存 ref、非用户陈述。

**③ 四个提交是否都在远端分支上？提供命令证据。**
**是。** 证据链：①`git ls-remote` 返回远端 SHA == 本地 HEAD；
②四个提交 `git merge-base --is-ancestor <c> HEAD` 均为 `True`（4/4）。两者结合即证明
`52165ca`、`bfb9fd0`、`62c86bf`、`ca86b0b` 全部可达自远端 `refs/heads/master`。
原文见 `git_sync_evidence.txt` §3 与 §8。

**④ 有无已跟踪修改、暂存内容或未解释的新增文件？区分有意保留的未跟踪项。**
- 已跟踪修改：**0**
- 暂存内容：**空**（`git diff --cached --name-status` 无输出）
- 未解释的新增文件：**无**
- 有意保留的未跟踪项：**85 个 `??` 条目**
  （U6.4.1 登记的 83 + 本任务单 1 + 本任务报告目录 1），
  已按 `reports/`、`scripts/`、`artifacts/`、`md/` 分类登记，`intentional=yes`；
  另有 1 个被 `.gitignore` 的 `*.db` 规则遮蔽的空壳目录（§6.2）

**⑤ 默认启动是否实测加载 136 类 V2.1？两套候选是否各有触发样本、非目标对照是否不触发？**
**是。** `num_classes=136`、`model_loaded=true`、`model_error=null`，
启动日志 `model ready: version=v2_1_136classes_candidate arch=resnet18 classes=136`。
- `collie-pair` 触发：`border_collie/n02106166_416.jpg` → `group_id=collie-pair`、`triggered=true`、得分和 100.0
- `four-breed-bully` 触发：`american_pit_bull_terrier_132.jpg` → `group_id=four-breed-bully`、`triggered=true`、得分和 100.0
- 非目标对照：`beagle_101.jpg` → `triggered=false`（不渲染候选区）

三张样本的**原始 Top-1、Top-K 与分数全部未被替换**。

**⑥ V1.1/V2.1 权重、数据、正式 DB/uploads 与配置是否保持一致？**
**全部一致（11/11 通过）。** V1.1 `89ef468f…`、V2.1 `423e218a…` 与期望逐字符相同；
V2.1 另三文件可读且哈希已记录；五个数据目录文件数/字节已记录；
正式 DB **142 条 + integrity ok**；正式 `uploads/` **142 文件**；
默认 `weights_path`/`class_names_path` 指向 V2.1、`candidate_group_enabled=True`。

**⑦ 是否需要重跑完整测试？依据是什么？**
**不需要。** 依据：HEAD 精确等于 `ca86b0b`、远端 SHA 相同、`M`=0 且本任务零代码改动，
符合任务 §4 的免测条件。引用的 U6.4.1 结果为 268 passed / 85 passed(12 files) / build 成功。
若人工要求重跑，命令见 `reports/u6_4_1_git_finalization/test_results_*.md`。

**⑧ 是否可以转入毕业设计交付准备？若不可以，列出具体阻塞项。**
**可以，无阻塞项。** 四条前置条件全部满足：远端与本地 SHA 一致、无已跟踪修改、
冒烟测试通过、保护对象一致。

---

## 8. 遗留事项（不阻塞，供交付准备时注意）

1. **`reports/` 与 `scripts/` 仍为未跟踪** —— 依仓库既有惯例的有意排除，**非遗漏**。
   若希望报告或个别长期脚本入库，需单独决定。
2. **`md/` 13 个任务单未入库** —— 是否入库取决于团队约定。
3. **`scripts/` 中 4 个脚本含 `E:\CatDogBreedNet` 硬编码**
   （`audit_v2_data_sources.py`、`build_clean_split.py`、`build_v2_dataset.py`、`diagnose_dataset.py`），
   如未来入库需先参数化。
4. **`reports/u6_5_remote_sync_wrapup+/`**（§6.2）为本任务命令笔误产生的空壳目录，可安全删除；
   按"不删除 runtime 目录"的约束保留待人工处理。
5. **`model_weights` 字段无法单独区分版本**（V1.1/V2.1 同名 `best_model.pth`）。
   建议后续在 `/api/health` 或 checkpoint 元数据中暴露独立的 `model_version` 标识，
   避免每次都要靠 `num_classes` + 启动日志交叉判断。

---

## 9. 阶段结论与下一步

**U6.4.1 的四个提交已同步远端；U5.5/V2.1 默认模型接入与两套相近犬种候选提示的运行版本，
已完成阶段验收。**

下一步可转入**毕业设计交付准备**，需整理：

- 模型与数据集说明（V1.1 37 类 / V2.1 136 类、`data/v2_processed` 划分与规模）
- 评估方法与实验结果（136/37/99 三组指标、两套候选策略的触发率与阈值依据）
- 系统演示流程（前端上传 → 原始 Top-K → 候选区 → 用户选择）
- 回退步骤（`CATDOG_WEIGHTS_PATH` / `CATDOG_CLASS_NAMES_PATH` 切回 V1.1）
- 局限性与未达标方向

> **关于边牧专项的表述要求**：U6 与 U6.1 的结论是**未达到冻结标准**
> （`exp06` 最好成绩 5/6，双向错误 5 > 4、`collie` F1 三 seed 均值未稳定越过 +0.10），
> 因此该方向应表述为**"未达到冻结标准的研究方向"**，
> **不得称为"已优化成功"**。本报告中"阶段验收通过"仅指**运行版本可用**，与模型精度提升无关。

---

## 10. 本任务边界执行情况

| 约束 | 执行情况 |
|---|---|
| `git fetch` / `pull` / `push` | **均未执行** |
| `git add` / `commit` / `reset` / `clean` / `checkout` / `restore` / `stash` / `rebase` / `amend` | **均未执行** |
| 训练脚本 | **未运行** |
| `data/v2_processed/test` 访问 | **0 次** |
| 正式 `data/app.db` / `uploads/` 写入 | **0 次** |
| 删除/移动未跟踪文件、报告、脚本、权重、runtime | **未执行** |
| 修改 `.gitignore` / 阈值 / 候选算法 / 默认模型配置 | **未执行** |
| 代码改动 | **0 行** |

**只读命令清单**：`rev-parse`、`branch --show-current`、`log`、`status`、`diff`、
`diff --cached`、`ls-remote`、`merge-base --is-ancestor`。

---

## 11. 交付物

| 文件 | 内容 |
|---|---|
| `acceptance_report.md` | 本报告（含 8 个必答问题） |
| `git_sync_evidence.txt` | 7 条只读 git 命令原文 + 四个 commit 祖先判定 + tracking ref 对照 + 判据汇总 |
| `runtime_smoke.json` | health 全字段、启动日志身份行、三张样本的输入/输出/断言明细 |
| `protection_summary.json` | 权重与元数据哈希、五数据目录统计、正式 DB、uploads、默认配置、11 项检查 |
| `runtime/`（目录） | 隔离实例的临时 SQLite 与 uploads，**保留作审计证据，未清理** |

---

**阶段核验完成。未执行任何 Git 写操作，未训练，未访问 test split，未写正式 DB/uploads，未清理工作区。**
