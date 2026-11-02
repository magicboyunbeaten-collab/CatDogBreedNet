# U6.4：分组提交计划（**命令尚未执行**）

> ⚠️ **本文件仅为建议文本。U6.4 是审核阶段，未执行任何 Git 写操作。**
> 当前 HEAD 仍为 `547c55d`，`git diff --cached` 为空，索引未被修改。
> 需人工审核并**明确批准**后，才进入单独的 U6.4 执行阶段。
>
> 生成时间：2026-10-21
> 数据来源：`file_by_file_review.csv`（105 行）、`mixed_changes_analysis.md`、`working_tree_before.txt`

---

## 0. 分组总览

| 组 | 类别 | 文件数 | 可否独立提交 | 建议顺序 |
|---|---|---:|---|---:|
| **A** | 正式运行代码 | **10** | 是（但需 B 组同批或紧随） | 1 |
| **B** | 配套测试 | **9** | 依赖 A | 2 |
| **C** | 启动入口 | **2** | 依赖 A 的默认配置 | 3 |
| **D** | 训练基础设施（独立） | **4** | **是，与 A/B/C 无符号依赖** | 4（或任意） |
| **E** | 任务单/文档 | **12** | 是（**需用户决定是否入库**） | 5（或任意） |
| **F** | 暂不提交 | **68** | — | 不提交 |

合计 105 行 = 18 个已跟踪修改 + 87 个未跟踪项（含本任务新增的 2 个脚本与本报告目录）。

> **禁止** `git add .` / `git add -A` / 目录级通配符。下文每组列出**完整相对路径**。

---

## 1. 依赖关系图

```
A 正式运行代码（10）
├──> B 配套测试（9）       —— B 的 import/断言直接引用 A 的符号与常量
└──> C 启动入口（2）       —— .bat 检查 A 的默认模型路径是否成对存在

D 训练基础设施（4）        —— 与 A/B/C 无符号依赖，可独立提交
E 任务单（12）             —— 无依赖，可任意顺序
F 不提交（68）             —— 见 do_not_commit.md
```

**关键依赖**（不满足则测试失败）：

| 依赖方 | 被依赖 | 具体符号 |
|---|---|---|
| `tests/test_candidate_group.py` | `backend/app/services/candidate_group.py` | `CANDIDATE_GROUP`、`COLLIE_PAIR_*`、`build_*_group`、`resolve_candidate_group` |
| `tests/test_collie_pair_candidate.py` | 同上 + `backend/app/schemas.py` | `GROUP_ID_COLLIE_PAIR`、`CandidateGroupInfo`、`PredictResponse` |
| `tests/test_api.py` | `backend/app/schemas.py`、`main.py` | `HealthResponse.model_weights`、`CandidateGroupInfo` |
| `frontend/tests/breedNames.test.js` | `frontend/src/utils/breedNames.js` | `BREED_NAMES_ZH`（136 条）、`CANDIDATE_GROUP` |
| `frontend/tests/historyView.test.js` | `frontend/src/utils/breedNames.js` | `getBreedDisplayName`（136 条映射） |
| `frontend/tests/predictionResult.test.js` | `frontend/src/components/PredictionResult.vue` | `.candidate-block`、`candidateCount`、`.candidate-group-id` |
| `frontend/tests/colliePairCandidate.test.js` | 同上 | `group_id`、`candidateSubtitle` |
| `tests/test_train_extensions.py` | `ml/train.py` | `initialize_from_checkpoint`、`head_transferred` |
| `ml/train.py`（pair 参数分支） | `ml/u6_pair_training.py` | `PairColorJitterDataset`、`make_pair_weighted_sampler` |

---

## 2. 分组 A：正式运行代码（10 个文件）

**纳入理由**：日常启动入口（`启动后端.bat` → `uvicorn backend.app.main:app`）实际加载并执行
这些文件；U6.3 已用运行证据确认其行为（`/api/health` `num_classes=136`、两套候选策略按
Top-1 分发、关闭开关后原始预测逐位不变）。

| # | 路径 | tracked | 改动 | 混合 | 说明 |
|---|---|---|---:|---|---|
| 1 | `backend/app/config.py` | M | +38/−3 | 否 | 新增 `DEFAULT_MODEL_DIR`、`_env_bool`、`class_names_path`；默认翻 V2.1 + 开关 True |
| 2 | `backend/app/main.py` | M | +18/−1 | **是** | 错配错误信息 + 透传 + health `model_weights` |
| 3 | `backend/app/schemas.py` | M | +57/−0 | **是** | `CandidateBreedItem`/`CandidateGroupInfo`(含 `group_id`)/`model_weights` |
| 4 | `backend/app/services/predictor.py` | M | +33/−2 | **是** | 错配明确失败 + `probabilities` 透传 |
| 5 | `backend/app/services/candidate_group.py` | **??** | 新文件 | **是** | 两套策略 + Top-1 分发 + V1.1 安全退回 |
| 6 | `backend/app/routes/predict.py` | M | +11/−0 | 否 | 候选组 try/except 接线 |
| 7 | `frontend/src/utils/breedNames.js` | M | +133/−11 | **是** | 136 条映射 + 候选四类常量 |
| 8 | `frontend/src/components/PredictionResult.vue` | M | +242/−1 | **是** | 候选区 + 动态数量 + `group_id` + 文案声明 |
| 9 | `ml/predict.py` | M | +15/−2 | 否 | `probabilities` 透传（**修正 U6.3 的 G7 误分类**） |
| 10 | `ml/predictor.py` | M | +8/−3 | 否 | 同上（**修正 U6.3 的 G7 误分类**） |

**建议提交顺序**：本组内一次性提交（`candidate_group.py` 必须与 `predictor.py`/`predict.py`
同批，否则 `resolve_candidate_group` 的分发逻辑不完整）。

```powershell
# 【尚未执行】分组 A
git add backend/app/config.py
git add backend/app/main.py
git add backend/app/schemas.py
git add backend/app/services/predictor.py
git add backend/app/services/candidate_group.py
git add backend/app/routes/predict.py
git add frontend/src/utils/breedNames.js
git add frontend/src/components/PredictionResult.vue
git add ml/predict.py
git add ml/predictor.py
git diff --cached --name-status   # 必须恰好 10 行，逐一核对
```

**建议 commit message**：

```
feat(推理): 接入 V2.1 136 类默认模型与两套相近犬种候选策略

默认模型与类别映射
- config.py: 新增 DEFAULT_MODEL_DIR 指向 artifacts/v2_1_136classes_seed42，
  并新增独立 class_names_path（CATDOG_CLASS_NAMES_PATH），权重与类名表
  必须配对；两者类别数不一致时启动阶段明确失败，不静默降级
- config.py: 新增 _env_bool()，候选总开关默认 True
- main.py: 透传 class_names_path / candidate_group_enabled；
  /api/health 新增 model_weights（仅文件名，不暴露绝对路径）
- services/predictor.py: 类别数错配时重抛含两侧计数与两个真实路径的错误
  （数量相同但名称不同时保留原索引级错误，不破坏既有断言）
- 启动默认回退：V1.1 的 37 类文件仍在 artifacts/ 根目录原样保留，
  用 CATDOG_WEIGHTS_PATH / CATDOG_CLASS_NAMES_PATH 即可切回

两套并行候选策略（按原始 Top-1 分发，互不干扰）
- four-breed-bully: APBT / AmStaff / SBT / American Bulldog
  mass >= 0.30, margin <= 0.40, 版本 val-2026-10-19-four-breed-b1
- collie-pair: collie / border_collie
  mass >= 0.30, margin <= 0.30, 版本 val-2026-10-21-collie-pair-v1
- CandidateGroupInfo 新增可选 group_id（默认 None，向后兼容）
- 组内得分严格由完整 softmax 归一化（p_i / group_mass * 100），
  不硬编码 50/50；ml/predict.py 与 ml/predictor.py 透传完整 probabilities，
  避免把 Top-K 外候选当作 0 分（该向量不出现在 API 响应中）
- V1.1（37 类）缺少两组候选成员，两套策略均安全返回 None，不抛异常

前端
- breedNames.js: BREED_NAMES_ZH 由 37 条扩到 136 条（旧 37 条原样保留）
- PredictionResult.vue: 候选区按 group_id 渲染，图例候选数量动态计算，
  明确声明"不是整体识别置信度"且"不保证候选中一定包含正确品种"；
  用户选择仅存组件状态，不写数据库、不覆盖模型预测

验证（报告见 reports/u6_3_default_runtime_and_freeze/）
- pytest 265 passed / npm test 85 passed (12 files) / npm run build 成功
- 默认配置隔离实例：/api/health num_classes=136，两套候选均按预期触发
- 关闭总开关后 14/14 样本原始 Top-1、Top-K、分数逐位不变
```

---

## 3. 分组 B：配套测试（9 个文件）

**纳入理由**：锁定 A 组行为；同时修正因 A 组改动而**必然失败**的既有断言
（如 `historyView.test.js` 中原用 `border_collie` 当"未映射标签"的用例）。

| # | 路径 | tracked | 改动 | 混合 | 备注 |
|---|---|---|---:|---|---|
| 1 | `tests/test_api.py` | M | +25/−0 | **是** | health `model_weights` + 候选组断言 |
| 2 | `tests/test_predictor_service.py` | M | +37/−0 | **是** | 错配失败 + 候选组安全返回 |
| 3 | `tests/test_candidate_group.py` | **??** | 新文件 | **是** | 四类 + collie-pair 后端回归 |
| 4 | `tests/test_collie_pair_candidate.py` | **??** | 新文件 | 否 | 15 个 collie-pair 专属用例 |
| 5 | `frontend/tests/breedNames.test.js` | M | +90/−17 | **是** | 136 类完整性 + 旧 37 兼容 + 候选四类 |
| 6 | `frontend/tests/historyView.test.js` | M | +35/−2 | **是** | 未映射用例改用真正未知标签 |
| 7 | `frontend/tests/predictionResult.test.js` | **??** | 新文件 | **是** | 13 个候选区用例（含 U5.3 数量动态化） |
| 8 | `frontend/tests/predictionResultAcceptance.test.js` | **??** | 新文件 | **是** | **依赖 `reports/` 下未跟踪 JSON，需人工决策** |
| 9 | `frontend/tests/colliePairCandidate.test.js` | **??** | 新文件 | 否 | 6 个 collie-pair 前端用例 |

> ⚠️ **提交前必须先决定第 8 项的去留**（三选一）：
> ① 破例把 `reports/v2_1_four_breed_candidate_implementation/acceptance_api_responses.json`
> 一并提交；② 把该测试改为内置 fixture（需改代码，**本轮不做**）；③ 暂不提交该测试。
> 若选 ③，其余 8 个文件仍可正常提交与运行。

```powershell
# 【尚未执行】分组 B（示例为"选 ③ 暂不提交第 8 项"）
git add tests/test_api.py
git add tests/test_predictor_service.py
git add tests/test_candidate_group.py
git add tests/test_collie_pair_candidate.py
git add frontend/tests/breedNames.test.js
git add frontend/tests/historyView.test.js
git add frontend/tests/predictionResult.test.js
git add frontend/tests/colliePairCandidate.test.js
git diff --cached --name-status
```

**建议 commit message**：

```
test: 补齐默认模型接入与两套候选策略的回归测试

后端
- test_api.py: /api/health 的 model_weights 断言 + 旧响应（无该字段）兼容
- test_predictor_service.py: 类别数错配必须失败并给出两侧计数与两个文件名；
  以及"不静默降级"用例
- test_candidate_group.py（新增）: 四类 bully 全部触发/不触发/归一化/Top-K 外
  候选/不改写原始预测/V1.1 安全/开关关闭；U6.2 的 group_id、独立阈值与版本、
  按 Top-1 分发
- test_collie_pair_candidate.py（新增）: 15 个 collie-pair 专属用例，含
  "不硬编码 50/50"与"API 不暴露概率向量"

前端
- breedNames.test.js: 由写死 37 条改为 136 类完整性 + 旧 37 类子集兼容 +
  边牧/柯利/边境梗互不混淆 + 候选四类中文名
- historyView.test.js: "未映射标签回退英文"用例改用真正未知标签
  （border_collie 自 U5.5 起已有中文名），并新增旧 37/新 99 类均显示中文
- predictionResult.test.js（新增）: 候选区渲染、图例数量动态化、
  null/undefined/triggered=false 均不渲染
- colliePairCandidate.test.js（新增）: 两候选中文名与数量、得分和约 100%、
  文案无必然正确暗示、用户选择不改 Top-K、按 group_id 区分两套策略
```

---

## 4. 分组 C：启动入口（2 个文件）

**纳入理由**：日常启动入口的默认模型路径检查与回退提示属"默认启动行为"的一部分。
`启动前端.bat` **未修改**，不在本组。

| # | 路径 | tracked | 改动 | 混合 |
|---|---|---|---:|---|
| 1 | `启动后端.bat` | M | +28/−9 | 否 |
| 2 | `启动系统.bat` | M | +12/−2 | 否 |

```powershell
# 【尚未执行】分组 C
git add "启动后端.bat"
git add "启动系统.bat"
git diff --cached --name-status
```

**建议 commit message**：

```
chore(启动): 启动脚本检查 V2.1 默认模型并附 V1.1 回退提示

- 启动后端.bat / 启动系统.bat: 模型路径检查从 artifacts/best_model.pth
  改为 artifacts/v2_1_136classes_seed42/ 下的 best_model.pth 与 class_names.json
- 两者仅以 if not defined CATDOG_WEIGHTS_PATH / CATDOG_CLASS_NAMES_PATH
  读取环境变量（不设置任何 CATDOG_*），因此用户显式回退到 V1.1 时不会被覆盖
- 缺失时输出可直接复制的回退命令，避免用户只能看到"未找到模型"
- 启动前端.bat 未改动
```

---

## 5. 分组 D：训练基础设施（4 个文件，**独立成组**）

**纳入理由**：任务 §3-C 明确要求"此组不应混入生产功能提交"。本组与线上推理无符号依赖，
但已被 U6/U6.1 实验使用，且含 **U4 / U6-C / U6 warm-start 三类来源**。

| # | 路径 | tracked | 改动 | 混合 | 来源 |
|---|---|---|---:|---|---|
| 1 | `ml/train.py` | M | +289/−18 | **是** | **U6-C** pair-only 通道 + `--image-size`；**U6** warm-start 分类头继承修复；**U4** 早前训练扩展 |
| 2 | `ml/dataset.py` | M | +15/−7 | **是** | **U6-C** `image_size` 参数；**U4** 既有 |
| 3 | `ml/u6_pair_training.py` | **??** | 新文件 | 否 | **U6-C** 纯新增 |
| 4 | `tests/test_train_extensions.py` | M | +181/−1 | **是** | **U6-C/U6**；**U4** 既有 |

```powershell
# 【尚未执行】分组 D
git add ml/train.py
git add ml/dataset.py
git add ml/u6_pair_training.py
git add tests/test_train_extensions.py
git diff --cached --name-status
```

**建议 commit message**：

```
feat(训练): pair-only 训练通道、image_size 与 warm-start 分类头继承修复

本提交只涉及训练工具，不改变线上推理路径（线上走 ml/predictor.py 的
eval transform，不使用 build_dataloaders）。

U6-C 边牧专项训练能力
- ml/u6_pair_training.py（新增）: PairColorJitterDataset（仅 collie /
  border_collie 施加 ColorJitter）、make_pair_weighted_sampler（仅两类加权）、
  parse_jitter、pair_sample_share
- ml/train.py: 新增 --pair-color-jitter / --pair-sampler-weight / --image-size，
  三者默认值均等价于原基线行为；生效参数写入 experiment_config.json
- ml/dataset.py: build_datasets / build_dataloaders 新增 image_size 参数
  （默认 224，向后兼容）

U6 warm-start 修复（影响实验可信度）
- ml/train.py: initialize_from_checkpoint 在类别名与顺序完全一致时连 fc.*
  一起继承（记录 head_transferred=True），仅在类别数不同时重建分类头；
  permitted_missing 同步收紧，任何必需参数未加载即抛错

U4 既有训练扩展（本次首次入库）
- --init-from / --monitor / --lr-head / --lr-backbone / --augment 等
  以及 AUGMENT_PRESETS

验证
- 5 个 U6 实验的 experiment_config.json 均记录 head_transferred=True、
  init_from.sha256 与 V2.1 一致；张量级比对确认 fc.weight / fc.bias 逐位一致
- tests/test_train_extensions.py 覆盖分类头继承、张量数量精确匹配、异常必须抛错
```

---

## 6. 分组 E：任务单/文档（12 个文件，**需用户决定是否入库**）

**纳入理由**：项目既有惯例保留 `md/` 下任务单（有追溯价值）。
**但**：这 12 个文件**全部为未跟踪**，且是否入库取决于团队对"任务单是否属于仓库内容"的约定。
**本计划不代为决定**——请人工确认"入库"或"整组排除"。

| # | 路径 |
|---|---|
| 1 | `md/U5.1_APBT纳入四类候选组离线评估任务.md` |
| 2 | `md/U5.2_方案B1四类相近犬种候选组正式实现任务.md` |
| 3 | `md/U5.4_候选组同图一致性与前端回归测试任务.md` |
| 4 | `md/U5.5_V2.1正式接入与边牧准确率改进计划.md` |
| 5 | `md/U6.1_低学习率纠偏与边牧专项对照实验任务.md` |
| 6 | `md/U6.2_柯利与边境牧羊犬双候选提示实施任务.md` |
| 7 | `md/U6.3_默认启动行为核验与安全固化.md` |
| 8 | `md/U6.4_Git安全固化_审核与提交计划.md` |
| 9 | `md/V2.1_136类别模型训练任务.md` |
| 10 | `md/V2.1_相近犬种候选提示与边牧复核整合任务.md` |
| 11 | `md/V2.1_误分类诊断与APBT_AmStaff数据审计任务.md` |
| 12 | `md/u6_border_collie_improvement_plan_修订版.md` |

```powershell
# 【尚未执行】分组 E —— 仅在人工确认"任务单入库"后执行
git add "md/U5.1_APBT纳入四类候选组离线评估任务.md"
git add "md/U5.2_方案B1四类相近犬种候选组正式实现任务.md"
git add "md/U5.4_候选组同图一致性与前端回归测试.md"
git add "md/U5.5_V2.1正式接入与边牧准确率改进计划.md"
git add "md/U6.1_低学习率纠偏与边牧专项对照实验任务.md"
git add "md/U6.2_柯利与边境牧羊犬双候选提示实施任务.md"
git add "md/U6.3_默认启动行为核验与安全固化.md"
git add "md/U6.4_Git安全固化_审核与提交计划.md"
git add "md/V2.1_136类别模型训练任务.md"
git add "md/V2.1_相近犬种候选提示与边牧复核整合任务.md"
git add "md/V2.1_误分类诊断与APBT_AmStaff数据审计任务.md"
git add "md/u6_border_collie_improvement_plan_修订版.md"
git diff --cached --name-status
```

> 注意：上例第 3 行的文件名请以 `git ls-files --others --exclude-standard` 的实际输出为准
> （本文件写作 `md/U5.4_候选组同图一致性与前端回归测试.md`，完整名为
> `md/U5.4_候选组同图一致性与前端回归测试任务.md`）。**提交前必须逐条核对实际路径**。

**建议 commit message**：

```
docs: 归档 U5.x / U6.x 任务单与边牧改进计划

仅文档，不含代码或产物。
```

---

## 7. 分组 F：暂不提交（68 项）

详见 `do_not_commit.md`。**不在本文件重复列出**，以免与那份文档不同步。

---

## 8. 建议执行顺序与每组后的验证

| 步骤 | 操作 | 验证命令 |
|---:|---|---|
| 1 | 提交分组 A | `git diff --cached --name-status`（应恰好 10 行）；提交后 `pytest tests/test_predictor_service.py -q` |
| 2 | 提交分组 B | `git diff --cached --name-status`；提交后 `pytest tests/ -q` 与 `cd frontend; npm test` |
| 3 | 提交分组 C | `git diff --cached --name-status`（应恰好 2 行） |
| 4 | 提交分组 D | `git diff --cached --name-status`；提交后 `pytest tests/test_train_extensions.py -q` |
| 5 | （可选）提交分组 E | `git diff --cached --name-status`（应恰好 12 行） |

每组提交后建议立即运行：

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q
cd frontend; npm test; npm run build
```

**若任一步的 `git diff --cached --name-status` 与预期行数/路径不符 → 立即停止，
不要继续提交下一组，先人工核查暂存区。**

---

## 9. 提交前必须核对的事项

- [ ] `git diff --cached --name-status` 逐行与上文清单一致（**不允许多、不允许少**）
- [ ] 暂存区中**没有任何** `artifacts/`、`data/`、`uploads/`、`.cache/`、`reports/`
      路径（除非第 3 节第 8 项的 JSON 破例入库并已明确记录）
- [ ] 未跟踪的 `scripts/`（41 个）与 `reports/`（12 个）目录**未进入暂存区**
- [ ] 每个混合改动文件已在 commit message 中列明覆盖范围
- [ ] 已人工决定 `predictionResultAcceptance.test.js` 的去留（三选一）
- [ ] 已人工决定 `md/` 是否入库
- [ ] 每组提交后立即跑回归，确认无失败

---

## 10. 明确未执行的操作

本文件中的所有 `git add` / `git commit` 命令**均未执行**。
U6.4 期间实际执行的 Git 命令仅有：

```powershell
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

全部为**只读子命令**；HEAD 未变、索引未变。
