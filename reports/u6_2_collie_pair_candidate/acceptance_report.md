# U6.2：柯利牧羊犬 / 边境牧羊犬双候选提示 — 验收报告

> **策略标识**：`collie-pair`　**阈值版本**：`val-2026-10-21-collie-pair-v1`
> **测试集访问次数 = 0**（所有样本均来自 `data/v2_processed/val`）
> **生成时间**：2026-10-21

---

## 0. 验收总览

| 层级 | 结果 |
|---|---|
| 后端全量 `pytest tests/ -q` | **265 passed**（基线 250 + 新增 15） |
| 四类 bully 组既有测试 | **54 passed**（无回归） |
| 前端全量 `npm test` | **85 passed / 12 files**（基线 79 + 新增 6） |
| 前端 `npm run build` | **成功**（1.69 s） |
| 隔离环境 API 验收 | **58 / 58 通过** |
| 真实页面验收（候选开启） | **28 / 28 通过** |
| 真实页面验收（候选关闭） | **4 / 4 通过** |
| 保护核对 | **全部一致** |

---

## 1. 自动化测试

### 1.1 后端：`tests/test_collie_pair_candidate.py`（15 个用例）

覆盖任务 §4.1 全部 12 项 + 3 项附加：

| # | 要求 | 用例 | 结果 |
|---|---|---|---|
| 1 | Top-1=collie 且满足阈值触发 | `test_collie_pair_triggers_when_top1_collie_and_thresholds_met` | PASS |
| 2 | Top-1=border_collie 且满足阈值触发 | `test_collie_pair_triggers_when_top1_border_collie` | PASS |
| 3 | pair_margin 超阈值不触发 | `test_collie_pair_not_triggered_when_margin_too_large` | PASS |
| 4 | pair_mass 低于阈值不触发 | `test_collie_pair_not_triggered_when_mass_too_low` | PASS |
| 5 | Top-1 在两类外不触发 | `test_collie_pair_not_triggered_when_top1_outside_pair` | PASS |
| 6 | 得分按完整概率归一化、和约 100% | `test_collie_pair_scores_normalised_from_full_probabilities` | PASS |
| 7 | Top-K 外候选不当 0 | `test_collie_pair_candidate_outside_topk_uses_real_probability` | PASS |
| 8 | 原始 Top-1/Top-K/分数不被改写 | `test_collie_pair_does_not_modify_original_predictions` | PASS |
| 9 | 四类组成员/阈值/版本/代表样本不变 | `test_four_breed_group_unchanged_by_collie_pair` | PASS |
| 10 | V1.1 安全返回不崩溃 | `test_collie_pair_returns_none_for_v11_class_space` | PASS |
| 11 | 关闭总开关两种候选均不显示 | `test_master_switch_disables_both_strategies` | PASS |
| 12 | API 不暴露概率向量、DB 无新字段 | `test_api_response_never_exposes_full_probability_vector` | PASS |
| 附 | 成员与版本独立性 | `test_collie_pair_members_and_version_are_independent` | PASS |
| 附 | 按 Top-1 分发策略 | `test_resolve_dispatch_selects_strategy_by_top1` | PASS |
| 附 | `group_id` 可选（向后兼容） | `test_candidate_group_info_group_id_is_optional` | PASS |

**关键断言示例**（不硬编码 50/50）：0.6032 / 0.3955 归一化后必须是
**60.3985 / 39.6015**，而不是各 50。

### 1.2 前端：`frontend/tests/colliePairCandidate.test.js`（6 个用例）

覆盖任务 §4.2 全部 6 项：

| # | 要求 | 结果 |
|---|---|---|
| 1 | 两个候选中文名与数量正确；四类组仍显示四项 | PASS |
| 2 | 双候选组分数合计约 100%，标注「候选组内相对得分」 | PASS |
| 3 | 文案不暗示其中必然有正确答案 | PASS |
| 4 | 用户选择后只更新「你选择的品种」，不改模型 Top-1/Top-K/原始分数 | PASS |
| 5 | `candidate_group` 为 null / undefined / triggered=false 均不显示候选区 | PASS |
| 6 | 两种候选组按组标识正确渲染，无三/四候选硬编码混淆 | PASS |

> 用例 3 首轮**失败**，暴露出组件说明文案缺少任务 §3 要求的
> 「也不保证候选中一定包含正确品种」。已补充该声明后复测通过——
> 这是测试驱动发现的真实文案缺口，非断言误差。

---

## 2. 隔离环境 API 验收（58/58）

**环境**：`scripts/accept_collie_pair_api.py` 复用 `build_isolated_app`——
真实 V2.1 权重 + 136 类映射 + **临时 SQLite + 临时 uploads**，
未访问或写入正式 `data/app.db` 与项目 `uploads/`。

### 2.1 样本（全部来自 validation，未编造）

| 类型 | 数量 | 说明 |
|---|---|---|
| 双候选**触发**图 | **3** | 全部来自阈值扫描的真实触发样本 |
| 双候选**不触发**对照 | **3** | Top-1 属两类但分差 > 0.30 |
| 四类 bully 代表图 | 1 | `american_pit_bull_terrier_132.jpg`（U5.1 样本） |
| 非目标犬种 | 1 | beagle |

### 2.2 触发图实测结果

| 图片 | Top-1 | group_id | mass | margin | 组内得分 |
|---|---|---|---:|---:|---|
| `border_collie/n02106166_416.jpg` | border_collie | collie-pair | 0.999177 | 0.201679 | 边境牧羊犬 60.0923% / 柯利牧羊犬 39.9077% |
| `border_collie/n02106166_549.jpg` | **collie** | collie-pair | 0.998652 | 0.207796 | 柯利牧羊犬 60.4038% / 边境牧羊犬 39.5962% |
| `border_collie/n02106166_884.jpg` | border_collie | collie-pair | 0.568896 | 0.252474 | 边境牧羊犬 72.1898% / 柯利牧羊犬 27.8102% |

三项候选中文名正确、组内得分和 **100.000000**、
得分严格等于各自原始概率归一化、原始 Top-1 不被替换。

### 2.3 同一张图串行 5 次

| 次 | Top-1 | Top-1 分数 | 触发 | 候选顺序 |
|---|---|---:|---|---|
| 1 | border_collie | 0.60042800 | True | border_collie;collie |
| 2 | border_collie | 0.60042800 | True | border_collie;collie |
| 3 | border_collie | 0.60042800 | True | border_collie;collie |
| 4 | border_collie | 0.60042800 | True | border_collie;collie |
| 5 | border_collie | 0.60042800 | True | border_collie;collie |

**Top-1 分数最大绝对差 = 0.000e+00**；触发状态、候选成员与顺序、组分完全一致。

### 2.4 开关开/关对照

| 项目 | 开启 | 关闭 |
|---|---|---|
| `candidate_group` | `{group_id: "collie-pair", triggered: true, ...}` | `None` |
| 原始 Top-1 | border_collie | border_collie（一致） |
| 原始 Top-1 分数 | 0.60042800 | 0.60042800（**差 0.0**） |
| 原始 Top-K 全数组 | — | **逐位相同** |

### 2.5 其它核验

| 项目 | 结果 |
|---|---|
| `/api/health` | `num_classes: 136`、`model_weights: best_model.pth`、默认模型仍 V2.1 |
| 临时 DB 表字段 | `['id','image_path','predicted_breed','confidence','top_k_json','inference_ms','created_at']` —— **无候选组字段** |
| DB 记录数 | 13 = 上传次数（3 触发 + 3 不触发 + 1 四类 + 1 非目标 + 5 重复） |
| API 不暴露概率 | 响应中**无** `probabilities` 字段 |
| 非目标犬种 | 不触发，且**未误入双候选策略**（`group_id=four-breed-bully`，`reason="top-1 不在候选组内"`） |

---

## 3. 真实页面验收（Playwright + 系统 Chrome）

**环境**：隔离后端（临时 DB/uploads + 真实 V2.1 权重，端口 8000）+
真实 Vite 前端（端口 5173）+ 系统 Chrome（`channel:'chrome'`，未下载浏览器）。

### 3.1 候选开启（28/28）

| 场景 | 结果 |
|---|---|
| 1. 触发图 A（Top-1=border_collie） | **9/9** —— 双候选区、`group_id=collie-pair`、两项候选、中文名「柯利牧羊犬/边境牧羊犬」、副标题如实、得分和 **100.0000%**、Top-K 3 行不变、Top-1 中文名、图例含 `val-2026-10-21-collie-pair-v1` |
| 2. 触发图 B（Top-1=collie） | **4/4** —— 双候选区、2 项、得分和 100.0000%、Top-1「柯利牧羊犬」 |
| 3. 用户选择交互 | **4/4** —— 点第 2 项后独立显示，提示「模型首选仍为 柯利牧羊犬（原始分 60.32%），未被替换」，Top-K 未变 |
| 4. 触发图 C | **3/3** —— 双候选区、2 项、得分和 100.0000% |
| 5. 不触发图（分差 0.6299） | **4/4** —— 候选区**完全不出现**、无「你选择的品种」、Top-K 3 行、Top-1「柯利牧羊犬」 |
| 6. 非目标犬种（beagle） | **2/2** —— 候选区不出现、Top-1「比格犬」 |
| 7. 文案核查 | **2/2** —— 含「不保证候选中一定包含正确品种」；不含「其中必有一个/必然/一定是」 |

### 3.2 候选关闭（4/4）

| 场景 | 结果 |
|---|---|
| 8. 关闭后复测同一张图 | **4/4** —— 候选区消失、无「你选择的品种」、Top-K 仍 3 行、Top-1 仍「边境牧羊犬」 |

### 3.3 截图（`screenshots/`）

| 文件 | 场景 |
|---|---|
| `01_collie_pair_trigger_A.png` | 触发图 A，双候选区（两项 + 组标识 + 副标题） |
| `02_collie_pair_trigger_B.png` | 触发图 B（Top-1=collie） |
| `03_user_selection.png` | 用户选择第 2 项后的独立显示 |
| `04_collie_pair_trigger_C.png` | 触发图 C |
| `05_non_trigger.png` | 不触发图，无候选区 |
| `06_non_target_breed.png` | 非目标犬种，无候选区 |
| `07_switch_off.png` | 关闭候选功能后同一张图 |

**可复现步骤**：

```powershell
cd E:\CatDogBreedNet
# 1. 启动隔离后端（候选开启）
.venv\Scripts\python.exe scripts\run_four_breed_backend.py --enable-candidate-group
# 2. 启动前端（另开窗口）
cd frontend; npm run dev
# 3. 运行页面验收（再开一个窗口）
cd E:\CatDogBreedNet
$env:PW_PATH="E:\CatDogBreedNet\.cache\pw\node_modules\playwright"
$node="E:\CatDogBreedNet\tools\node\node-v24.21.0-win-x64\node.exe"
& $node scripts/page_accept_collie_pair.mjs --scenario on
# 4. 关闭候选：停止后端，改用 --disable-candidate-group 重启，再跑
& $node scripts/page_accept_collie_pair.mjs --scenario off
```

---

## 4. 保护核对（全部一致）

| 检查项 | 结果 |
|---|---|
| V1.1 `artifacts/best_model.pth` | `89ef468f…a256` **一致** |
| V2.1 `best_model.pth` | `423e218a…21e1` **一致** |
| V2.1 `class_names.json` / `model_version.json` / `experiment_config.json` | **一致**（只读加载） |
| 五个数据目录 | 文件数与总字节 **一致** |
| 正式 `data/app.db` | **142 条**，`integrity_check: ok` |
| 项目 `uploads/` | **142 文件** |
| 默认 `weights_path` / `class_names_path` | 均指向 V2.1 目录，**未改** |
| `candidate_group_enabled` 默认值 | **True**（U5.5 接入后状态），**未改** |
| 四类组成员 / 阈值 / 版本 | `(APBT, AmStaff, SBT, American Bulldog)` / 0.30 / 0.40 / `val-2026-10-19-four-breed-b1`，**未改** |
| `.bat` 启动入口 | **未改** |
| 训练 / test split | **未运行任何训练脚本** / **访问 0 次** |
| 既有报告目录 | 只读引用，**未覆盖、未清理** |
| 后台进程 | 8000 与 5173 **已释放** |

`protection_snapshot_before.json` / `_after.json` 自动比对：**全部受保护对象一致**。

---

## 5. 未解决的限制

1. **触发率极低（0.1443%）**，且真实 `collie` 永远不会被提示（0/16）——
   模型对真实柯利的 pair_margin 全部 ≥ 0.7131。
2. **样本量极小**：触发样本仅 3 张，全部是真实 `border_collie`。
   **不得**据此宣称候选提示提高了分类准确率。
3. **保守阈值的代价**：margin 收紧到 0.30 会漏掉部分真实竞争样本
   （margin 0.30–0.40 区间内有 1 张真实 `border_collie` 未被提示）；
   放宽到 0.40 则会引入 `bernese_mountain_dog` 组外误触发。
4. **mass 阈值未被数据区分**：0.10–0.50 在该子集内等效。
5. 本验收覆盖 3 张触发图 × 2 个开关状态 + 3 张不触发图 + 1 张非目标犬种，
   **非全量巡检**。
6. 未做并发一致性测试（本轮为串行请求）。

---

## 6. Git 状态（未提交、未清理）

HEAD 仍为 `547c55d`。本轮改动：

```
M  backend/app/schemas.py
M  backend/app/services/candidate_group.py
M  frontend/src/components/PredictionResult.vue
?? scripts/u6_2_collie_pair_threshold.py
?? scripts/accept_collie_pair_api.py
?? scripts/page_accept_collie_pair.mjs
?? tests/test_collie_pair_candidate.py
?? reports/u6_2_collie_pair_candidate/
```

**未执行** `git add` / `git commit` / `git reset --hard` / `git clean` / 大范围 checkout；
既有改动与工作区全部原样保留。

---

**验收完成并停止，等待人工审核。未训练、未切换模型、未写数据库、未访问 test split、未自动启用任何功能。**
