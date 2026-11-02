# U5.4 候选组同图一致性与前端回归测试报告

> **性质**：测试与验收完善（**不是**模型训练，**不是**正式系统发布）
> **候选模型**：V2.1 `artifacts/v2_1_136classes_seed42/best_model.pth`（136 类）
> **正式模型**：V1.1 `artifacts/best_model.pth`（37 类），**未切换、未改动**
> **候选组版本**：`val-2026-10-19-four-breed-b1`（四类，mass 0.30 / margin 0.40）
> **报告目录**：`reports/v2_1_four_breed_consistency_review/`
> **生成时间**：2026-10-19
> **测试集访问记录**：**0**（只使用 validation 图片）

---

## 0. 总结论

**全部通过。** 前端候选数量文案已有自动化单测覆盖（**13 个用例**，原 8 + 新增 5）；
同一张图片在同一开关配置下连续 5 次请求**完全一致**（Top-1 分数最大绝对差
**0.000e+00**，候选成员与顺序、组内得分全部逐位相同）；
开/关对照只改变候选提示，**原始 Top-1、Top-K 数组逐位未变**。

**未观察到任何非预期不一致**（`unexpected_inconsistency: []`）。
回归测试与构建全部通过，保护核对全部一致。

---

## 1. 测试设置

| 项目 | 配置 |
|---|---|
| 验收图片 | `data/v2_processed/val/american_pit_bull_terrier/american_pit_bull_terrier_132.jpg`（与 U5.3 同一张） |
| 权重 | **只读** V2.1 `best_model.pth`，`num_classes = 136` |
| 类别映射 | **只读** V2.1 `class_names.json`（136 类） |
| 隔离方式 | 复用 `scripts/run_four_breed_backend.py::build_isolated_app`（自建 Settings + PredictorService，**不改生产默认值**） |
| 临时 SQLite | 开：`runtime_on/app.db`；关：`runtime_off/app.db` —— 与正式 `data/app.db` **物理隔离** |
| 临时 uploads | 开：`runtime_on/uploads/`；关：`runtime_off/uploads/` —— 与项目 `uploads/` **物理隔离** |
| 请求方式 | `fastapi.testclient.TestClient` + `with` 上下文（驱动 lifespan），上传**原始文件字节**（不重新编码，避免像素漂移） |
| 重复次数 | 开关开启 **5 次**；开关关闭 **1 次** |
| batch size | **1**（单张图片请求） |

**为什么必须用隔离启动器**：`PredictorService` 会用默认 `artifacts/class_names.json`
（**37 类**）校验 checkpoint；直接把 `CATDOG_WEIGHTS_PATH` 指向 136 类的 V2.1 会因
class count mismatch 失败。启动器自行注入 136 类映射，**未修改任何生产配置**。

---

## 2. 前端单元回归测试（新增 5 个用例，`frontend/tests/predictionResult.test.js`）

### 2.1 新增用例

| 用例 | 验证内容 | 结果 |
|---|---|---|
| **I** | 四个候选时图例文案解析出 **4**（正则 `([0-9]+\|[一二两三四五六])\s*个候选`，兼容阿拉伯/中文数字）；且仍保留"候选组内相对得分""不是"的含义 | PASS |
| **J** | 三个候选 fixture → 图例解析为 **3**，`.candidate-row` 为 3，`ElRadio` 为 3，三候选中文名全部渲染 → **证明文案与渲染都未硬编码 3 或 4** | PASS |
| **K** | 参数化 **2 / 3 / 4** 候选 → 解析数量恒等于 `candidates.length` 与 `.candidate-row` 数；且组内得分和 ≈ 100 | PASS |
| **L** | `candidate_group` 键**缺失（`undefined`）**→ `.candidate-block` 与 `.user-choice` 均不存在；原始 Top-K 仍为 3 行（补齐此前仅测 `null` 与 `triggered=false` 的缺口） | PASS |
| **M** | 点击第 3 个候选（SBT）后：`predictions` **全数组逐项 deep equal**（breed + confidence）、`.prediction-row` **每行文本未变**、原始 `42.00%` 分数文本仍在、模型首选仍为 APBT | PASS |

### 2.2 前端测试总数

| 范围 | 结果 |
|---|---|
| `tests/predictionResult.test.js` | **13 passed**（原 8 + 新增 5） |
| `frontend` 全量 | **79 passed / 11 files**（原 74 + 新增 5） |

**未修改** `PredictionResult.vue`（`candidateCount` 已是动态 computed），
**未修改**任何中文文案。

---

## 3. 同一张图片重复请求结果（开关开启 × 5）

### 3.1 稳定性核对

| 检查项 | 实测 | 结果 |
|---|---|---|
| `candidate_group.triggered` 是否相同 | `[True, True, True, True, True]` | PASS |
| 四个候选成员及顺序是否一致 | `APBT;AmStaff;SBT;American Bulldog`（5 次完全相同，且与四类 B1 定义一致） | PASS |
| 原始 Top-1 标签是否一致 | `american_pit_bull_terrier`（5 次相同） | PASS |
| **原始 Top-1 分数最大绝对差** | **`0.000e+00`**（min = max = `0.4672210000`） | PASS |
| 四项组内得分是否由完整 Softmax 归一化 | 最大偏差 **`4.607e-05`**（来自 4 位小数的展示取整，非逻辑误差） | PASS |
| 组内得分总和 | `[100.0, 100.0, 100.0, 100.0, 100.0]` | PASS |
| `threshold_version` 恒定 | `val-2026-10-19-four-breed-b1` | PASS |
| 四候选原始 Softmax 分数 5 次一致 | **1 种取值** | PASS |
| 原始 Top-K 全数组 5 次一致 | **1 种取值** | PASS |

### 3.2 每次请求的候选得分（示例：第 1 次，其余 4 次完全相同）

| 候选 | 原始 Softmax | 组内相对得分 |
|---|---|---|
| `american_pit_bull_terrier` | 0.467221 | **54.4621%** |
| `american_staffordshire_terrier` | 0.3905 | **45.5313%** |
| `staffordshire_bull_terrier` | 0.000038 | **0.0045%** |
| `american_bulldog` | 0.000018 | **0.0021%** |
| **合计** | `group_mass = 0.857883` | **100.0000%** |

> 这张是 APBT 与 AmStaff 高度竞争的典型样本（margin 仅 0.0766 ≪ 0.40），
> 正是候选提示设计意图覆盖的场景。
>
> **关于浮点误差的说明**：本任务所有请求均为 **batch = 1**，实测逐位一致
> （最大绝对差 0.0）。U5 曾实测 batch=1 vs batch=32 存在 **5.73e-4** 级
> GPU 非确定性，但该量级比阈值（mass 0.30 / margin 0.40）小 3 个数量级以上，
> **不足以改变任何阈值判定**。本轮**未修改任何阈值**。

---

## 4. 同一张图片开 / 关对照

### 表 A — `EXPECTED_BY_DESIGN`（开关按设计改变展示，**不是缺陷**）

| 项目 | 开启 | 关闭 | 是否符合设计 |
|---|---|---|---|
| API 返回 `candidate_group` | 有（`triggered = true`，四候选） | `null`（字段存在但为空） | **是** |
| 前端候选区 | 显示四候选 | **不显示** | **是** |
| "你选择的品种"区 | 显示 | **不显示** | **是** |
| 原始 Top-1 标签 | `american_pit_bull_terrier` | `american_pit_bull_terrier` | **一致** |
| 原始 Top-1 分数 | `0.4672210000` | `0.4672210000` | **一致（差 0.0）** |
| 原始 Top-K 全数组 | 见 CSV | **逐位相同** | **一致** |

**结论**：开关**只影响候选提示**，不改变模型权重、原始分类排序或正式配置。
U5.3 中 `01_trigger_apbt.png` 与 `05_switch_off.png` 的差异属于此类
**设计预期**，不应误判为同配置下的随机变化。

### 表 B — `UNEXPECTED_INCONSISTENCY`（同一开关配置下的非预期差异）

| 检查项 | 结果 |
|---|---|
| 同开关下 5 次请求之间的任何差异 | **无**（`unexpected_inconsistency: []`） |

---

## 5. 通过项汇总（17/17）

| # | 检查项 | 结果 |
|---|---|---|
| 1 | 开启态 `triggered` 全部相同 | PASS |
| 2 | 开启态 `triggered` 为 `True` | PASS |
| 3 | 四候选成员与顺序 5 次完全一致 | PASS |
| 4 | 候选成员与四类 B1 定义一致 | PASS |
| 5 | 原始 Top-1 标签 5 次完全一致 | PASS |
| 6 | 原始 Top-1 分数 5 次一致（max_abs_diff = 0） | PASS |
| 7 | `threshold_version` 恒为四类 B1 | PASS |
| 8 | 组内得分之和每次 ≈ 100% | PASS |
| 9 | 组内得分严格等于原始概率归一化 | PASS |
| 10 | 四候选原始 Softmax 分数 5 次一致 | PASS |
| 11 | 原始 Top-K 全数组 5 次一致 | PASS |
| 12 | 开启态返回候选组 | PASS |
| 13 | 关闭态不返回候选组 | PASS |
| 14 | 关闭态 `triggered` 字段不存在 | PASS |
| 15 | 开/关两态原始 Top-1 标签一致 | PASS |
| 16 | 开/关两态原始 Top-1 分数一致 | PASS |
| 17 | 开/关两态原始 Top-K 全数组一致 | PASS |

## 6. 失败项

**无。**

---

## 7. 回归验证（实际执行）

| 命令 | 结果 |
|---|---|
| `.venv\Scripts\python.exe -m pytest tests/ -q` | **244 passed**（与基线一致；本轮未新增后端用例，只新增前端用例与检查脚本） |
| `cd frontend; npm test` | **79 passed / 11 files**（基线 74 + 新增 5） |
| `cd frontend; npm run build` | **构建成功**（834 ms；chunk >500 kB 警告为既有情况） |

---

## 8. 保护核对

| 检查项 | 结果 |
|---|---|
| V1.1 `artifacts/best_model.pth` SHA256 | `89ef468f199c6d1550fec2638c5ea6f8ef7ad543e57f8ec82c4263c121b1a256` **一致** |
| V2.1 `best_model.pth` / `class_names.json` / `model_version.json` / `experiment_config.json` | SHA256 **一致**（只读加载） |
| `artifacts/class_names.json` | 仍 **37 类**，未被 136 类映射覆盖 |
| 五个数据目录 + V1 备份 | 文件数与总字节 **一致** |
| 正式 `data/app.db` | **142** 条，`integrity_check: ok`（未被触碰） |
| 项目 `uploads/` | **142 文件**，与验收前一致 |
| 后端 `weights_path` 默认值 | `artifacts/best_model.pth`，**未改** |
| `candidate_group_enabled` 默认值 | **`False`**，**未改** |
| 训练 | **未调用任何训练脚本，未生成 V2.2 权重** |
| test split | **访问次数 0** |
| 既有报告目录 | `page_acceptance` 8 / `candidate_implementation` 7 / `apbt_four_breed_candidate_eval` 13 / `candidate_ui_review` 13 / `diagnostics` 20 / `coat_pitbull_diagnostics` 31 —— **全部不变** |

前后快照：`protection_snapshot_before.json` / `protection_snapshot_after.json`
（`scripts/diagnostic_protection_snapshot.py` 自动比对通过：**「前后对比：全部受保护对象一致」**）。

---

## 9. 可复现步骤

```powershell
cd E:\CatDogBreedNet

# 1. 保护快照
.venv\Scripts\python.exe scripts\diagnostic_protection_snapshot.py `
  --phase before --out-dir reports\v2_1_four_breed_consistency_review

# 2. 同图一致性检查（开启 5 次 + 关闭 1 次）
.venv\Scripts\python.exe scripts\check_candidate_consistency.py

# 3. 前端单元测试（含新增 I–M 用例）
cd frontend
npm test
npm run build

# 4. 后端全量测试
cd ..
.venv\Scripts\python.exe -m pytest tests/ -q

# 5. 保护后比对
.venv\Scripts\python.exe scripts\diagnostic_protection_snapshot.py `
  --phase after --out-dir reports\v2_1_four_breed_consistency_review
```

---

## 10. 输出文件

| 文件 | 内容 |
|---|---|
| `consistency_report.md` | 本报告 |
| `same_image_repeated_requests.csv` | 6 行逐次请求明细（5 次开启 + 1 次关闭），含开关状态、Top-1、原始分数、是否触发、四候选 breed/原始分/组内得分、`group_mass`/`group_margin`、`group_score_sum` |
| `consistency_summary.json` | 17 项检查的机器可读结果与 `unexpected_inconsistency` 空表 |
| `protection_snapshot_before.json` / `_after.json` | 保护快照（自动比对通过） |
| `git_status_before.txt` | 任务开始前 `git status --short` 原文 |
| `runtime_on/` / `runtime_off/` | 隔离运行的临时 SQLite + uploads 副本（**非正式路径**，可按需清理） |

---

## 11. 未解决的限制

1. **只覆盖 1 张图片 × 1 个随机种子配置**。同图一致性已证，但这不等于
   "所有图片在所有硬件上都逐位一致"——GPU 跨 batch size 仍有 5.73e-4 级
   非确定性（U5 实测），只是远小于阈值。
2. **未做并发一致性测试**。本轮为串行请求；多请求并发时的预测器锁行为
   未在页面/API 层验证（`ml/predictor.py` 有 `self._lock`，但本轮未压测）。
3. **前端一致性只覆盖组件层**（vitest + @vue/test-utils），真实浏览器层的
   一致性验证见 U5.3 的页面验收报告（5 张截图），本轮未重复截图。
4. **候选功能默认仍关闭**，V2.1 尚未接入正式系统；本报告不构成上线结论。
5. **触发率仍低**（validation 四类 B1 约 12/2,079 ≈ 0.58%），本轮验证的是
   "触发时行为稳定"，不是"提高触发率"。

---

## 12. 本轮改动清单

| 文件 | 类型 | 内容 |
|---|---|---|
| `frontend/tests/predictionResult.test.js` | 修改 | 追加用例 I–M（5 个）与 `parseCandidateCount` / `buildGroup` / 三个 fixture 辅助 |
| `scripts/check_candidate_consistency.py` | **新增** | 同图 5 次请求 + 开/关对照的一致性检查脚本 |
| 本目录 6 项产出 | **新增** | 见第 10 节 |

**未修改**：`PredictionResult.vue`、任何中文文案、`backend/**`、`ml/**`、
`artifacts/**`、`data/**`、任何既有报告目录。

---

## 13. Git 状态（未提交、未清理）

本轮**未执行 `git commit`**、未 `git add .`、未 `git reset --hard`、未 `git clean`、
未大范围 checkout，未清理任何既有未提交改动。开始前状态见 `git_status_before.txt`。

---

**验收完成并停止，等待人工审核。未自动开启正式候选功能、未切换正式模型、
未开始 V2.2 训练。**
