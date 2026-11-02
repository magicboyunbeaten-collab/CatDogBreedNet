# U6.4.1：四个提交的完整记录

> 起始 HEAD：`547c55dd96b5d2a9aca71c58458f4192e55b38f5`（`547c55d v2训练前`，`master`）
> 结束 HEAD：`ca86b0b`
> 提交顺序：**A → B → C → D**（严格按任务 §4）
> **未推送远端**、**未 amend**、**未 force push**。

---

## 0. 提交一览

| 组 | commit | message | 文件数 | 变更 |
|---|---|---|---:|---|
| **A** | `52165ca` | Integrate V2.1 136-class prediction and candidate groups | **10** | +942 / −23 |
| **B** | `bfb9fd0` | Add regression tests for prediction and candidate UX | **9** | +2136 / −19 |
| **C** | `62c86bf` | Use V2.1 defaults in Windows launchers | **2** | +40 / −11 |
| **D** | `ca86b0b` | Extend training infrastructure for warm-start and pair experiments | **4** | +632 / −26 |
| — | 合计 | — | **25** | +3750 / −79 |

`git log -4 --oneline` 实测输出：

```
ca86b0b Extend training infrastructure for warm-start and pair experiments
62c86bf Use V2.1 defaults in Windows launchers
bfb9fd0 Add regression tests for prediction and candidate UX
52165ca Integrate V2.1 136-class prediction and candidate groups
```

---

## 1. A 组：正式运行代码

**commit**：`52165ca`　**message**：`Integrate V2.1 136-class prediction and candidate groups`

`git show --stat --oneline 52165ca`：

```
52165ca Integrate V2.1 136-class prediction and candidate groups
 backend/app/config.py                        |  41 ++-
 backend/app/main.py                          |  19 +-
 backend/app/routes/predict.py                |  11 +
 backend/app/schemas.py                       |  57 ++++
 backend/app/services/candidate_group.py      | 387 +++++++++++++++++++++++++++
 backend/app/services/predictor.py            |  35 ++-
 frontend/src/components/PredictionResult.vue | 243 ++++++++++++++++-
 frontend/src/utils/breedNames.js             | 144 +++++++++-
 ml/predict.py                                |  17 +-
 ml/predictor.py                              |  11 +-
 10 files changed, 942 insertions(+), 23 deletions(-)
 create mode 100644 backend/app/services/candidate_group.py
```

| # | 路径 | 状态 | 说明 |
|---|---|---|---|
| 1 | `backend/app/config.py` | M | `DEFAULT_MODEL_DIR`、`class_names_path`、`_env_bool`；默认 V2.1 + 开关 True |
| 2 | `backend/app/main.py` | M | 错配错误信息 + 透传 + health `model_weights` |
| 3 | `backend/app/routes/predict.py` | M | 候选组 try/except 接线 |
| 4 | `backend/app/schemas.py` | M | `CandidateBreedItem` / `CandidateGroupInfo`(含 `group_id`) / `model_weights` |
| 5 | `backend/app/services/predictor.py` | M | 数量错配明确失败 + `probabilities` 透传 |
| 6 | `backend/app/services/candidate_group.py` | **A**（新） | 两套策略 + Top-1 分发 + V1.1 安全退回 |
| 7 | `frontend/src/components/PredictionResult.vue` | M | 候选区 + 动态数量 + `group_id` + 文案声明 |
| 8 | `frontend/src/utils/breedNames.js` | M | 136 条映射 + 候选四类常量 |
| 9 | `ml/predict.py` | M | `probabilities` 全量 softmax 透传 |
| 10 | `ml/predictor.py` | M | 同上 |

**提交前核对**：
- `git diff --cached --name-status` = **M 9 + A 1 = 10 项**，与本组名单集合完全相等（多出 0 / 缺少 0）
- 判据 1（暂存路径不在 `artifacts|reports|data|uploads|.cache|dist|md`）：通过
- 判据 2（新增行无 `E:\` / `C:\Users` 绝对路径）：通过
- 判据 3（无密钥特征）：通过
- 无二进制文件（`--numstat` 无 `-` 行）

**关于初筛误报（如实记录）**：首轮用朴素关键字扫描暂存 diff 时，`artifacts/`（2 处）与
`reports/`（5 处）命中。逐行检查后确认**全部是注释/文档中的路径引用**，例如：

```
#: 需要回退时用环境变量指向它们即可（见 reports/u5_5_v2_1_integration/rollback.md）。
* 键**完全等于** `artifacts/v2_1_136classes_seed42/class_names.json` 中的
```

没有任何来自这两个目录的**文件**被暂存。因此改为三条精确判据（按**路径**判定而非按文本），
全部通过后才提交。

**提交后 A 组相关测试**：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_candidate_group.py tests/test_api.py -q
```

结果：**87 passed**，退出码 **0**。

---

## 2. B 组：配套测试

**commit**：`bfb9fd0`　**message**：`Add regression tests for prediction and candidate UX`

`git show --stat --oneline bfb9fd0`：

```
bfb9fd0 Add regression tests for prediction and candidate UX
 frontend/tests/breedNames.test.js                 | 107 +++-
 frontend/tests/colliePairCandidate.test.js        | 222 ++++++++
 frontend/tests/historyView.test.js                |  37 +-
 frontend/tests/predictionResult.test.js           | 301 ++++++++++
 frontend/tests/predictionResultAcceptance.test.js | 368 ++++++++++++
 tests/test_api.py                                 |  25 +
 tests/test_candidate_group.py                     | 649 ++++++++++++++++++++
 tests/test_collie_pair_candidate.py               | 328 ++++++++++++
 tests/test_predictor_service.py                   | 118 ++++
 9 files changed, 2136 insertions(+), 19 deletions(-)
```

| # | 路径 | 状态 |
|---|---|---|
| 1 | `frontend/tests/breedNames.test.js` | M |
| 2 | `frontend/tests/colliePairCandidate.test.js` | **A**（新） |
| 3 | `frontend/tests/historyView.test.js` | M |
| 4 | `frontend/tests/predictionResult.test.js` | **A**（新） |
| 5 | `frontend/tests/predictionResultAcceptance.test.js` | **A**（新，本任务改为 inline fixture） |
| 6 | `tests/test_api.py` | M |
| 7 | `tests/test_candidate_group.py` | **A**（新） |
| 8 | `tests/test_collie_pair_candidate.py` | **A**（新） |
| 9 | `tests/test_predictor_service.py` | M（本任务 +3 个索引级错配用例） |

**提交前核对**：`--name-status` = **4 M + 5 A = 9 项**，集合完全相等；
`tests/test_train_extensions.py` **确认未混入**（属 D 组）；
三条安全判据通过；
`predictionResultAcceptance.test.js` 中已无 `readFileSync(` / `from 'node:` / `require('fs')`。

**⚠ 一次提交失败（如实记录）**：首次用 PowerShell here-string 直接传
`git commit -m <多行含引号的中文英文混合文本>` 时，PowerShell 把消息里的一段
（含 `without`）当成了 pathspec，git 报
`error: pathspec 'without' did not match any file(s) known to git`，**提交未发生**
（HEAD 仍为 `52165ca`，暂存区仍恰为 9 项，工作区未受损）。
随后把消息写入 `.cache/u641_B_msg.txt` 并用 `git commit -F` 提交成功。
C、D 组同样使用 `-F`，未再出现该问题。

**提交后 B 组相关测试**：

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q      # 268 passed
cd frontend; npm test                             # 85 passed / 12 files
```

均退出码 **0**。

---

## 3. C 组：日常启动入口

**commit**：`62c86bf`　**message**：`Use V2.1 defaults in Windows launchers`

`git show --stat --oneline 62c86bf`：

```
62c86bf Use V2.1 defaults in Windows launchers
 启动后端.bat | 37 ++++++++++++++++++++++++---------
 启动系统.bat | 14 ++++++++++++--
 2 files changed, 40 insertions(+), 11 deletions(-)
```

| # | 路径 | 状态 |
|---|---|---|
| 1 | `启动后端.bat` | M |
| 2 | `启动系统.bat` | M |

**提交前核对**：`--name-status` = **2 项**（恰为本组）；
`git diff --cached -- "启动后端.bat" "启动系统.bat"` 逐行审查，与 U6.4 审核内容一致：

- `set "MODEL_DIR=%ROOT%artifacts\v2_1_136classes_seed42"`（默认模型目录改指 V2.1）
- `if not defined CATDOG_WEIGHTS_PATH` / `if not defined CATDOG_CLASS_NAMES_PATH`
  （**只读**语义，跳过默认路径检查）
- 缺失时输出可复制的 V1.1 回退命令
- 定义时回显已指定的环境变量

**只读语义的机器核验**（`scripts` 侧正则扫描）：

| 文件 | 真正 `set CATDOG_*` | 仅在 `echo` 提示中出现赋值 | 引用 V2.1 目录 | BOM |
|---|---|---|---|---|
| `启动后端.bat` | **无** | `CATDOG_CLASS_NAMES_PATH`、`CATDOG_DEVICE`、`CATDOG_WEIGHTS_PATH` | True | 无 |
| `启动系统.bat` | **无** | `CATDOG_CLASS_NAMES_PATH`、`CATDOG_WEIGHTS_PATH` | True | 无 |

→ 确认两个脚本**没有任何真实的 `CATDOG_*` 赋值**，只有错误提示里的 `echo set ...` 文本。

**提交后 C 组相关检查**：`.bat` 编码与关键行静态检查通过（无 BOM、行数 68 / 81、均含 V2.1 目录）；
`npm run build` 重跑 **退出码 0**。

---

## 4. D 组：训练基础设施（独立成组）

**commit**：`ca86b0b`　**message**：`Extend training infrastructure for warm-start and pair experiments`

`git show --stat --oneline ca86b0b`：

```
ca86b0b Extend training infrastructure for warm-start and pair experiments
 ml/dataset.py                  |  22 ++-
 ml/train.py                    | 307 ++++++++++++++++++++++++++++++++++++---
 ml/u6_pair_training.py         | 147 ++++++++++++++++++++++
 tests/test_train_extensions.py | 182 +++++++++++++++++++++++++++++--
 4 files changed, 632 insertions(+), 26 deletions(-)
 create mode 100644 ml/u6_pair_training.py
```

| # | 路径 | 状态 | 来源 |
|---|---|---|---|
| 1 | `ml/dataset.py` | M | **U6-C** `image_size` + **U4** 既有 |
| 2 | `ml/train.py` | M | **U6-C** pair-only/`--image-size` + **U6 warm-start 修复** + **U4 训练扩展** |
| 3 | `ml/u6_pair_training.py` | **A**（新） | **U6-C** 纯新增 |
| 4 | `tests/test_train_extensions.py` | M | **U6-C/U6** + **U4** 既有 |

**提交前核对**：`--name-status` = **3 M + 1 A = 4 项**，集合完全相等；
**确认 A/B/C 组文件未混入**（无 `backend/`、`frontend/`、`*.bat`）；
三条安全判据通过。

**三类来源在 diff 中的存在性核验**（新增行计数）：

| 标志 | 新增行数 | 归属 |
|---|---:|---|
| `pair_color_jitter` | 4 | U6-C |
| `pair_sampler_weight` | 4 | U6-C |
| `image_size` | 12 | U6-C |
| `head_transferred` | 2 | U6 warm-start 修复 |
| `init_from` | 5 | U4 |
| `monitor` | 21 | U4 |

**commit body 完整披露三类来源**（非只有标题），明确写明：

1. U6-C 边牧专项训练能力（`u6_pair_training.py` + 三个新参数，默认值等价于原基线）
2. U6 warm-start 修复（原先无条件跳过分类头，导致 136→136 也把 `fc.*` 置随机；
   现改为类别名与顺序完全一致时连 `fc.*` 一起继承并记录 `head_transferred`）
3. U4 训练扩展（本次首次入库）

并注明"本提交只涉及训练工具，线上推理路径不变"。

**提交后 D 组相关测试**：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_train_extensions.py -q
```

结果：**39 passed**，退出码 **0**。

---

## 5. 每组硬性检查的执行情况汇总

| 检查项 | A | B | C | D |
|---|:--:|:--:|:--:|:--:|
| 1. 用 `git add --` 显式路径（无 `.`/`-A`/通配符） | ✅ | ✅ | ✅ | ✅ |
| 2. `--name-status` 与本组名单集合相等 | ✅ 10/10 | ✅ 9/9 | ✅ 2/2 | ✅ 4/4 |
| 3. 暂存路径不在禁止目录 | ✅ | ✅ | ✅ | ✅ |
| 4. 新增行无本地绝对路径 / 密钥 | ✅ | ✅ | ✅ | ✅ |
| 5. 提交后 `git log -1` / `show --stat` / `status` 记录 | ✅ | ✅ | ✅ | ✅ |
| 6. 组后相关测试 | ✅ 87 passed | ✅ 268 + 85 | ✅ build 0 | ✅ 39 passed |

**未发生**：`git add .`、`git add -A`、通配符暂存、`git reset`、`git clean`、
`git checkout`、`git restore`（工作区层面）、`git stash`、`git rebase`、
`git commit --amend`、强推、远端 push。
（`git restore --staged` 也**未使用**——四组暂存集合每次都一次校验通过。）

---

## 6. 复现命令（供审查）

```powershell
cd E:\CatDogBreedNet
git log -4 --oneline
git show --stat --oneline 52165ca
git show --stat --oneline bfb9fd0
git show --stat --oneline 62c86bf
git show --stat --oneline ca86b0b
git show --stat --oneline ca86b0b -- ml/train.py    # 三类来源的完整披露
git rev-parse HEAD                                  # ca86b0b...
```
