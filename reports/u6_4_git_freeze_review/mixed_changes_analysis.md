# U6.4：混合改动文件逐一分析（10 + 4 个）

> 本文件对应任务 §3-D。**本轮不编辑、不拆分任何源文件**；若需把混合改动拆成独立提交，
> 须另行制作独立补丁（见每个文件的"拆分方案"）。
>
> 审阅方式：`git diff -- <path>` 实际阅读（审阅深度见 `file_by_file_review.csv`
> 的 `review_depth` 列），**不依赖文件名或既有报告的分类**。
>
> 生成时间：2026-10-21

---

## 目录

- [任务指定的 10 个文件](#任务指定的-10-个文件)
- [本次额外发现的 4 个混合改动（新文件）](#本次额外发现的-4-个混合改动新文件)
- [汇总与拆分风险](#汇总与拆分风险)

---

## 任务指定的 10 个文件

### 1. `backend/app/main.py`

| 维度 | 结论 |
|---|---|
| **包含哪些功能** | ① `_safe_model_error` 识别 `class count mismatch` 并用正则解析两侧类别数，生成不带绝对路径的明确错误（**U5.5**）；② lifespan 中 `PredictorService(...)` 透传 `class_names_path` 与 `candidate_group_enabled`（**U5.5**；`candidate_group_enabled` 的透传同时是 **U5.2** 候选组接线的必要前提）；③ `/api/health` 新增 `model_weights` 字段（**U5.5**） |
| **是否运行必需** | **是**。模型加载与健康检查的唯一入口 |
| **整文件提交会带入什么** | 上述三项一次性全部进入同一次提交。三者都属于"V2.1 接入 + 候选组可用"这一整体目标，语义一致，**带入风险低** |
| **未覆盖或依赖风险** | `model_weights` 只暴露文件名，而 V1.1/V2.1 权重同名（`best_model.pth`），**无法单独据此判定版本**——已在 U6.3 报告中记录，属既有设计限制而非本次改动缺陷 |
| **拆分方案** | 若必须拆分：②③（U5.5）与 ①（U5.5 错误信息）本就可同组；真正跨任务的是 `candidate_group_enabled` 透传（U5.2 依赖）。建议**不拆**，在 commit message 中注明"透传 candidate_group_enabled 同时服务 U5.2 候选组接线" |

---

### 2. `backend/app/services/predictor.py`

| 维度 | 结论 |
|---|---|
| **包含哪些功能** | ① 类名校验失败时，**仅当两侧类别数不同**才重抛含两个真实路径与两侧计数的错误；数量相同但名称/顺序不同则保留 `verify_class_mapping` 原有的索引级错误（**U5.5**，该条件分支是为避免破坏既有测试而专门设计）；② 向候选组透传完整 `probabilities`（**U5.2/U6.2**） |
| **是否运行必需** | **是** |
| **整文件提交会带入什么** | 错配保护 + 候选组概率透传。两者都直接服务于"候选组能在 V2.1 下正确工作" |
| **未覆盖或依赖风险** | 条件分支依赖 `verify_class_mapping` 的消息格式（`class count mismatch: ... (X classes) ... (Y classes)`）；若上游改措辞，分支会静默失效。**当前无测试覆盖"数量相同名称不同时保留原消息"这一路径**，建议后续补测 |
| **拆分方案** | 不建议拆。①属配置安全、②属功能透传，但同文件同一次提交语义连贯 |

---

### 3. `frontend/src/components/PredictionResult.vue`

| 维度 | 结论 |
|---|---|
| **包含哪些功能** | ① 候选区整体渲染、`v-for` 候选行、`user-choice` 独立区（**U5.2**）；② 图例候选数量由硬编码"三个候选"改为 `candidateCount` 动态计算（**U5.3**，修复真实文案缺陷）；③ `group_id` 可见渲染（`.candidate-group-id` + `data-group-id`）、`collie-pair` 专属副标题、说明文案补充"**也不保证候选中一定包含正确品种**"（**U6.2**） |
| **是否运行必需** | **是**（前端核心展示组件） |
| **整文件提交会带入什么** | 三轮迭代一次性全部带入。由于 ③ 依赖 ② 的动态数量机制（否则两类组会显示错误的候选数），**拆开提交会导致中间状态不一致** |
| **未覆盖或依赖风险** | `predictionResultAcceptance.test.js` 依赖 `reports/` 下未跟踪的 JSON 回放数据；若报告不入库，该测试在新克隆环境会失败（见 `file_by_file_review.csv` 中该行） |
| **拆分方案** | **不建议拆**。②③ 有直接依赖关系；若强行拆分需先提交 ② 再提交 ③，但二者在同一文件的不同区域，git 层面可用 `git add -p` 实现——**需人工决定是否值得** |

---

### 4. `frontend/tests/breedNames.test.js`

| 维度 | 结论 |
|---|---|
| **包含哪些功能** | ① 断言由写死 37 条改为 136 类完整性 + 键唯一 + 名唯一 + 缺失 0（**U5.5**）；② 保留 V1.1 旧 37 类子集兼容断言（**U5.5**）；③ 边牧/柯利/边境梗中文名互不混淆（**U5.5/U6 背景**）；④ 候选四类中文名断言（**U5.2**） |
| **是否运行必需** | 否（测试），但**强烈建议随 A 组同批提交** |
| **整文件提交会带入什么** | 136 类映射断言 + 候选四类断言一起进入。二者都锁定 `breedNames.js` 的行为，**同批提交才能保证测试与实现同步** |
| **未覆盖或依赖风险** | 无。测试不依赖外部文件 |
| **拆分方案** | 不建议拆 |

---

### 5. `frontend/tests/historyView.test.js`

| 维度 | 结论 |
|---|---|
| **包含哪些功能** | ① "未映射标签回退英文原名"用例的样本由 `border_collie` 改为 `not_a_known_breed`——因为 U5.5 后 `border_collie` 已有中文名，原断言**必然失败**（**U5.5 引发**）；② 新增"旧 37 类与新 99 类历史标签都显示中文"用例（**U5.5**）；③ 其余为 U5 早前历史页测试 |
| **是否运行必需** | 否（测试） |
| **整文件提交会带入什么** | ①是**跟随 U5.5 的被动修改**（不改就会挂），③是既有内容。带入风险低 |
| **未覆盖或依赖风险** | 无 |
| **拆分方案** | 不建议拆。①③ 同文件，且 ① 必须与 `breedNames.js` 的 136 条映射**同时提交** |

---

### 6. `ml/dataset.py`

| 维度 | 结论 |
|---|---|
| **包含哪些功能** | ① `build_datasets` / `build_dataloaders` 新增 `image_size` 参数（默认 `IMAGE_SIZE`=224，**向后兼容**），train/val/test 三个 transform 同步使用（**U6-C，为 exp04/exp06 分辨率实验**）；② 既有 `AUGMENT_PRESETS` / `build_transforms`（**U4**） |
| **是否运行必需** | **否**（训练专用）。线上推理走 `ml/predictor.py` 的 eval transform，不使用 `build_dataloaders` |
| **整文件提交会带入什么** | U6-C 的 `image_size` + U4 既有内容。由于 U4 部分**从未提交**（HEAD 中该文件已是旧版），整文件提交等于把 U4 的既有改动一并首次入库 |
| **未覆盖或依赖风险** | `image_size` 默认值取自 `IMAGE_SIZE` 常量；若该常量被改动，默认行为会静默变化 |
| **拆分方案** | 与 D 组其他文件同批提交，commit message 注明"含 U4 既有改动首次入库 + U6-C image_size 新增" |

---

### 7. `ml/train.py`

| 维度 | 结论 |
|---|---|
| **包含哪些功能** | ① **U6-C**：`--pair-color-jitter`（仅 collie/border_collie 施加 ColorJitter）、`--pair-sampler-weight`（仅两类加权采样，默认 1.0=关闭）、`--image-size`；② **U6 warm-start 修复**：`initialize_from_checkpoint` 在类别名完全一致时连 `fc.*` 一起继承（`head_transferred=True`），类别数不同则重建头并断言，`permitted_missing` 同步收紧；③ **U4 早前训练扩展**：`--init-from`、`--monitor`、`--lr-head`、`--lr-backbone`、`--augment` 等 |
| **是否运行必需** | **否**（训练脚本，线上不调用） |
| **整文件提交会带入什么** | 三类来源一次性全部带入，合计 +289/−18，是本次工作区**最大的单文件改动** |
| **未覆盖或依赖风险** | ②的修复已被 U6 报告用**张量级逐位一致**证据验证（5 个旧实验 `head_transferred=True` + `torch.equal(fc.weight)`），风险低；①依赖 `ml/u6_pair_training.py`（同批提交）；③从未提交，属首次入库 |
| **拆分方案** | 任务明确要求训练工具**独立成组、不混入生产功能提交**。若要拆 ①②③ 需三个独立补丁，但它们在同一函数与同一 CLI 区块交织，**拆分成本高、易错**。建议整文件一次提交 + message 列明三来源 |

---

### 8. `tests/test_api.py`

| 维度 | 结论 |
|---|---|
| **包含哪些功能** | ① 新增 `test_health_reports_loaded_weights_name`、`test_health_response_model_weights_is_optional`（**U5.5**），并修改 `test_health_model_not_ready` 增加 `model_weights is None` 断言；② `FakePredictor` 新增 `weights_path = Path("fake.pth")` 以对齐真实服务；③ 既有候选组响应断言（**U5.2**） |
| **是否运行必需** | 否（测试） |
| **整文件提交会带入什么** | health 新字段断言 + 候选组断言。②是支撑①的必要改动 |
| **未覆盖或依赖风险** | 无 |
| **拆分方案** | 不建议拆 |

---

### 9. `tests/test_predictor_service.py`

| 维度 | 结论 |
|---|---|
| **包含哪些功能** | ① 新增 `test_class_count_mismatch_names_both_sides`（断言错误消息含两侧计数与两个文件名）、`test_class_count_mismatch_does_not_silently_fall_back`（**U5.5**）；② 既有 `class_names_path` 匹配用例与候选组安全返回用例（**U5.2**） |
| **是否运行必需** | 否（测试） |
| **整文件提交会带入什么** | 错配失败用例 + 候选组安全用例 |
| **未覆盖或依赖风险** | 无 |
| **拆分方案** | 不建议拆 |

---

### 10. `tests/test_train_extensions.py`

| 维度 | 结论 |
|---|---|
| **包含哪些功能** | ① 覆盖 `initialize_from_checkpoint` 的 136→136 分类头继承、加载键统计、异常必须抛错（**U6 warm-start 修复 + U6-C**）；② U4 早前训练扩展测试 |
| **是否运行必需** | 否（测试），但**必须与 `ml/train.py` 同批提交** |
| **整文件提交会带入什么** | U6 与 U4 的测试一起首次入库 |
| **未覆盖或依赖风险** | 无（依赖 `ml/train.py`，同批即可） |
| **拆分方案** | 与 D 组同批 |

---

## 本次额外发现的 4 个混合改动（新文件）

任务只点名了 10 个已跟踪修改文件。逐文件审阅中另外发现 **4 个未跟踪新文件同样包含多任务内容**，
虽为新文件（无"拆分"问题），但**提交说明必须如实反映其覆盖范围**：

### 11. `backend/app/services/candidate_group.py`（新文件）

| 维度 | 结论 |
|---|---|
| **包含哪些功能** | **两套并行策略**：四类 bully（`group_id=four-breed-bully`，mass 0.30 / margin 0.40，版本 `val-2026-10-19-four-breed-b1`，**U5.2**）+ collie-pair（`group_id=collie-pair`，mass 0.30 / margin 0.30，版本 `val-2026-10-21-collie-pair-v1`，**U6.2**）；`resolve_candidate_group` 按原始 Top-1 分发；两组均要求成员齐全否则返回 `None`（V1.1 安全退回）；`group_id` 字段与 `GROUP_ID_*` 常量（U6.2） |
| **是否运行必需** | **是** |
| **整文件提交会带入什么** | 两套策略一次入库。这是**唯一同时包含两套策略的文件**，commit message 必须同时说明 U5.2 与 U6.2 |
| **风险** | 若只提交四类部分而不提交 collie-pair 部分（或反之），`resolve_candidate_group` 的分发逻辑会不完整。**必须整文件提交** |

### 12. `frontend/tests/predictionResult.test.js`（新文件）

| 维度 | 结论 |
|---|---|
| **包含哪些功能** | 13 个用例覆盖：未触发不渲染、四类候选渲染、得分和 100、Top-K 不被替换、用户选择 props 未改、**图例候选数量动态化**（U5.3 修复"三个候选"文案缺陷）、null/undefined 不渲染 |
| **是否运行必需** | 否（测试） |
| **整文件提交会带入什么** | U5.2/U5.3/U5.4 三阶段的测试积累 |
| **风险** | 依赖 `PredictionResult.vue` 的 `candidateCount`（U5.3 修复）与 `group_id`（U6.2）——**必须与 A 组同批或更晚提交** |

### 13. `frontend/tests/predictionResultAcceptance.test.js`（新文件）

| 维度 | 结论 |
|---|---|
| **包含哪些功能** | 8 个用例，从 `reports/v2_1_four_breed_candidate_implementation/acceptance_api_responses.json` 回放响应做断言（U5.2/U5.3） |
| **是否运行必需** | 否（测试） |
| **整文件提交会带入什么** | 一个**依赖未跟踪报告产物**的测试 |
| **风险** | **明确风险**：`acceptance_api_responses.json` 位于 `reports/` 且未跟踪；若遵循"reports/ 不入库"的惯例，该测试在新克隆环境会因找不到文件而失败。**需人工决策**：①把该 JSON 一并提交（破例）②把测试改为内置 fixture ③暂不提交该测试 |

### 14. `tests/test_candidate_group.py`（新文件）

| 维度 | 结论 |
|---|---|
| **包含哪些功能** | 约 30+ 个用例，覆盖四类 bully 全部行为（U5.2）+ U6.2 的 `group_id`、独立阈值与版本、按 Top-1 分发、V1.1 安全 |
| **是否运行必需** | 否（测试） |
| **整文件提交会带入什么** | U5.2 与 U6.2 的测试 |
| **风险** | 依赖 `candidate_group.py` 的两套策略常量，**必须与 A 组同批或更晚提交** |

---

## 汇总与拆分风险

| 项目 | 数值 |
|---|---|
| 任务指定的混合改动文件 | **10** |
| 本次额外发现的混合改动（新文件） | **4** |
| **合计** | **14** |
| 其中运行必需 | 5（`main.py`、`predictor.py`、`PredictionResult.vue`、`candidate_group.py`、`schemas.py`） |

### 三条硬结论

1. **不可声称"可按任务干净切分"**：14 个文件含多任务内容，其中 `ml/train.py` 含三类来源
   （+289/−18），`PredictionResult.vue` 含三轮迭代且有直接依赖关系。
2. **不建议拆分**：除 `PredictionResult.vue` 理论上可用 `git add -p` 拆分外，其余文件的
   跨任务改动在同一函数/同一语义块内交织，**拆分成本高、易引入中间状态不一致**。
3. **一个必须人工决策的依赖风险**：`predictionResultAcceptance.test.js` 依赖 `reports/` 下
   未跟踪的 JSON。若坚持"reports/ 不入库"，该测试在新克隆环境会失败——
   **这不构成不提交 A 组的理由，但构成"提交 B 组前必须先决定该测试命运"的理由**。

### 若要拆分的通用方案（本轮不执行）

```powershell
# 仅对确需拆分的文件使用交互式暂存；执行前必须人工逐块确认
git add -p <path>
# 查看已暂存的块是否符合预期
git diff --cached -- <path>
# 不符合则取消暂存（不会丢失工作区改动）
git restore --staged <path>
```

> `git add -p` / `git restore --staged` 会**改变索引**，属于 Git 写操作。
> **U6.4 本轮不执行上述任何命令**，仅作为未来人工拆分时的参考文本。
