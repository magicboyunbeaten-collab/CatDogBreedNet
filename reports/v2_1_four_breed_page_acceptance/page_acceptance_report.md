# U5.3 四类相近犬种候选功能 — 真实页面验收报告

> **性质**：真实浏览器页面验收（Playwright + 系统 Chrome），非组件级 mock 测试
> **候选模型**：V2.1 `artifacts/v2_1_136classes_seed42/best_model.pth`（136 类）
> **正式模型**：V1.1 `artifacts/best_model.pth`（37 类），**未切换、未改动**
> **候选组版本**：`val-2026-10-19-four-breed-b1`（四类，mass 0.30 / margin 0.40）
> **报告目录**：`reports/v2_1_four_breed_page_acceptance/`
> **生成时间**：2026-10-19

---

## 0. 总结论

**页面验收通过。** 开启候选组时 **30/30** 项通过；关闭开关后 **4/4** 项通过。
四类候选区正确显示 APBT / AmStaff / SBT / American Bulldog 四项及中文名，
组内相对得分之和 ≈ 100%，原始 Top-K 与模型首选未被替换，用户选择独立呈现
且不覆盖模型预测，非候选图不展示候选区，关闭开关后恢复原有行为。

**发现并修正 1 处真实文案缺陷**：图例硬编码"仅在上述**三个**候选之间归一化"，
而实际展示四项。已改为按后端返回的候选数量动态渲染，修正后复测通过。
首轮失败证据与修正后通过证据均已留档（见第 4 节）。

**未发现功能性缺陷。** 所有数据流（概率、排序、得分归一化、DB 写入）均符合口径。

---

## 1. 验收环境（隔离，未触碰正式资源）

| 项目 | 配置 |
|---|---|
| 后端 | `scripts/run_four_breed_backend.py` 注入式启动，`http://127.0.0.1:8000` |
| 后端权重 | **只读** V2.1 `best_model.pth`，`num_classes = 136`（`/api/health` 已确认） |
| 后端类别映射 | **只读** V2.1 `class_names.json`（136 类） |
| 临时 SQLite | `reports/v2_1_four_breed_page_acceptance/runtime/app.db`（与 `data/app.db` **物理隔离**） |
| 临时 uploads | `reports/v2_1_four_breed_page_acceptance/runtime/uploads/`（与项目 `uploads/` **物理隔离**） |
| 前端 | `npm run dev`（Vite 8.3.4），`http://127.0.0.1:5173` |
| 浏览器 | Playwright 1.64.1 + **系统 Chrome**（`channel: 'chrome'`，未下载 chromium） |
| Playwright 安装位置 | `.cache/pw/`（**未写入 `frontend/package.json`**） |

**为什么需要注入式启动器**：`PredictorService` 会用默认
`artifacts/class_names.json`（**37 类**）校验 checkpoint；直接把
`CATDOG_WEIGHTS_PATH` 指向 136 类的 V2.1 会因 class count mismatch 失败、
`/api/predict` 返回 503。启动器自行构造 `Settings` 与
`PredictorService(class_names_path=V2.1)`，**未修改任何生产配置默认值**。

---

## 2. 验收样本（全部来自 validation split）

| 场景 | 图片 | 真实标签 | 期望 |
|---|---|---|---|
| A | `val/american_pit_bull_terrier/american_pit_bull_terrier_132.jpg` | APBT | Top-1 = APBT，四类触发 |
| B | `val/american_pit_bull_terrier/american_pit_bull_terrier_11.jpg` | APBT | Top-1 = AmStaff，四类触发 |
| C | `val/Abyssinian/Abyssinian_10.jpg` | 猫（非候选组） | **不触发** |
| D | 同 A（关闭开关后复测） | APBT | **不触发**，恢复原行为 |

**test split 访问次数：0。**

---

## 3. 通过项清单（开启开关：30/30）

### 3.1 场景 A — 触发图（Top-1 = APBT）

| # | 检查项 | 实测 |
|---|---|---|
| A1 | 候选区出现 | PASS |
| A2 | 标题为"外观相近的候选品种" | PASS |
| A3 | 候选行数量为 4 | 实际 4 |
| A4 | 单选按钮数量为 4 | 实际 4 |
| A5 | **四个中文名齐全且正确** | `["美国比特斗牛梗","美国斯塔福郡梗","斯塔福郡斗牛梗","美国斗牛犬"]` |
| A6 | **组内相对得分之和 ≈ 100%** | **99.99%** |
| A7 | 标注"候选组内相对得分" | PASS |
| A8 | 标注"不是整体识别置信度/真实概率/准确率" | PASS |
| A9 | 图例候选数量表述与实际一致 | 图例声明 **4** 个 / 实际 **4** 个 |
| A10 | 图例不残留"三个候选"表述 | PASS（修正后） |
| A11 | 原始 Top-K 仍为 3 行 | 实际 3 |
| A12 | **Top-1 为 APBT（模型首选未被替换）** | 美国比特斗牛梗 |
| A13 | Top-1 分数仍显示原始百分比 | **46.72%** |
| A14 | 提示语含"登记品种" | PASS |
| A15 | 提示语不暗示必有正确答案 | PASS |

### 3.2 场景 B — 用户选择交互

| # | 检查项 | 实测 |
|---|---|---|
| B1 | 默认已显示"你选择的品种"区块 | PASS |
| B2 | 默认选择为模型首选 | `model-top=true` |
| B3 | 点击第 2 个单选项后区块仍存在 | PASS |
| B4 | **用户选择值变为第 2 个候选** | 美国斯塔福郡梗 |
| B5 | 提示说明"模型首选仍为 … 未被替换" | "模型首选仍为 美国比特斗牛梗（原始分 46.72%），未被替换。" |
| B6 | **用户选择后原始 Top-1 未被替换** | 美国比特斗牛梗（前后一致） |
| B7 | **用户选择后原始 Top-1 分数未变** | 46.72% → 46.72% |
| B8 | 用户选择后候选区得分未变 | 前后一致 |

### 3.3 场景 C — 触发图 B（Top-1 = AmStaff）

| # | 检查项 | 实测 |
|---|---|---|
| C1 | 候选区出现 | PASS |
| C2 | 候选行数量为 4 | 实际 4 |
| C3 | 组内相对得分之和 ≈ 100% | **100.01%** |
| C4 | Top-1 为 AmStaff 且与场景 A 不同 | 美国斯塔福郡梗 |

### 3.4 场景 D — 非候选组图片（猫）

| # | 检查项 | 实测 |
|---|---|---|
| D1 | **候选区完全不出现** | PASS |
| D2 | "你选择的品种"区块不出现 | PASS |
| D3 | 原始 Top-K 仍正常显示 | 实际 3 行 |

### 3.5 关闭开关后（4/4）

| # | 检查项 | 实测 |
|---|---|---|
| E1 | **同一张触发图不再展示候选区** | PASS |
| E2 | 无"你选择的品种"区块 | PASS |
| E3 | 原始 Top-K 仍正常显示（3 行） | 实际 3 |
| E4 | Top-1 仍为 APBT（预测本身不受开关影响） | 美国比特斗牛梗 |

---

## 4. 失败项与修正记录

### 4.1 唯一失败项：图例文案"三个候选"与实际四项不符

| 项目 | 内容 |
|---|---|
| **首轮结果** | 28/30 通过，**2 项失败** |
| **失败检查项** | ① 图例候选数量表述与实际一致（四类）<br>② 图例不残留"三个候选"表述 |
| **实测文案** | 「候选组内相对得分（val-2026-10-19-four-breed-b1）—— 仅在上述**三个**候选之间归一化，不是整体识别置信度、真实概率或准确率」 |
| **问题性质** | 硬编码文案。U5.2 把候选组从三类扩到四类时，`PredictionResult.vue` 的图例文字未同步更新，**属真实用户可见的事实性错误**（界面显示四项却称"三个候选"）。 |
| **定位** | `frontend/src/components/PredictionResult.vue` 第 73–75 行 |

**修正方式（最小改动）**：

```vue
<!-- 修正前 -->
仅在上述三个候选之间归一化，<b>不是</b>整体识别置信度、真实概率或准确率；

<!-- 修正后 -->
仅在上述{{ candidateCount }}个候选之间归一化，<b>不是</b>整体识别置信度、
真实概率或准确率；
```

```js
// 新增：候选数量由后端返回的 candidates 长度决定
const candidateCount = computed(
  () => candidateGroup.value?.candidates?.length ?? 0
)
```

**为什么这样改**：不再写死数字，未来候选组成员变化时文案自动跟随，
从根上避免同类漂移。

**修正后复测**：**30/30 全部通过**，图例实测为"仅在上述**4**个候选之间归一化"。

### 4.2 修正过程中的一次断言误差（非产品问题）

修正后仍有 1 项失败，原因是我的断言期望中文数字"四个候选"，而 Vue 插值
渲染为阿拉伯数字"4个候选"。已把断言改为**解析任意数字形式并与实际候选数
比较**，而非做字符串字面匹配。此为用户侧测试脚本问题，不是产品缺陷。

### 4.3 修正前的失败证据（已留档）

首轮失败时的证据保存在 `page_acceptance_evidence_on.json` 的历史版本中；
本报告 4.1 节的实测文案即为该次运行的原始输出。

---

## 5. 截图证据

| 文件 | 场景 | 说明 |
|---|---|---|
| `screenshots/01_trigger_apbt.png` | A | Top-1 = APBT，四类候选区展开，含"你选择的品种" |
| `screenshots/02_trigger_amstaff.png` | C | Top-1 = AmStaff，四类候选区 |
| `screenshots/03_user_selection.png` | B | 点击第 2 个候选后，"你选择的品种"变为 AmStaff，模型首选仍为 APBT |
| `screenshots/04_non_candidate.png` | D | 猫图片，**无候选区**，仅原始 Top-3 |
| `screenshots/05_switch_off.png` | E | 关闭开关后同一张触发图，**无候选区** |

均为 `fullPage: true` 全页截图（1440×1000 视口）。

---

## 6. 可复现步骤

```powershell
cd E:\CatDogBreedNet

# 1. 启动隔离后端（候选组开启）
.venv\Scripts\python.exe scripts\run_four_breed_backend.py --enable-candidate-group

# 2. 另开终端启动前端
cd frontend; npm run dev     # http://127.0.0.1:5173

# 3. 安装 Playwright 到隔离目录（不写入 frontend/package.json）
$env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD="1"
npm install --prefix .cache\pw playwright --no-save --no-package-lock

# 4. 运行页面验收（开启场景：30 项检查）
$env:PW_PATH="E:\CatDogBreedNet\.cache\pw\node_modules\playwright"
node scripts\page_accept_four_breed.mjs --scenario on

# 5. 关闭候选组后复测（4 项检查）
#    先停止后端，改为：
.venv\Scripts\python.exe scripts\run_four_breed_backend.py --disable-candidate-group
node scripts\page_accept_four_breed.mjs --scenario off
```

**手工核对方式**：浏览器打开 `http://127.0.0.1:5173/predict`，
将 `data/v2_processed/val/american_pit_bull_terrier/american_pit_bull_terrier_132.jpg`
拖入上传区，点"开始识别"，即可看到四类候选区。

---

## 7. 报告口径核对（配合 `report_reconciliation.md`）

| 数字 | 含义 | 实测 |
|---|---|---|
| **19** | 来源**记录**数 | 16（U5.1 三清单）+ 3（对照） |
| **16** | 代表样本 CSV **行**数 | 7 + 5 + 4，含 4 行重复 |
| **12** | 四类触发**唯一图片**数 | 7（newly）+ 5（both），互斥 |
| **3** | 未触发对照数 | Abyssinian ×3 |
| **160** | API 验收**检查项**数 | 全部通过 |

**唯一图片合计 15 张**（12 触发 + 3 对照），与"19 条记录"不是同一口径。
详见 `report_reconciliation.md`（新建勘误文档，**未修改任何既有报告**）。

---

## 8. 保护核对

| 检查项 | 结果 |
|---|---|
| V1.1 `artifacts/best_model.pth` SHA256 | `89ef468f199c6d1550fec2638c5ea6f8ef7ad543e57f8ec82c4263c121b1a256` **一致** |
| V2.1 `best_model.pth` / `class_names.json` / `model_version.json` / `experiment_config.json` | SHA256 **一致**（只读加载） |
| `artifacts/class_names.json` | 仍为 **37 类**，未被 136 类映射覆盖 |
| 五个数据目录 + V1 备份 | 文件数与总字节 **一致** |
| 正式 `data/app.db` | 行数与 `integrity_check` **一致**（未被触碰） |
| 项目 `uploads/` | **142 文件**，与验收前一致 |
| 后端 `weights_path` 默认值 | `artifacts/best_model.pth`，**未改** |
| `candidate_group_enabled` 默认值 | `False`，**未改** |
| 训练 | **未调用任何训练脚本，未生成 V2.2 权重** |
| test split | **访问次数 0** |
| 既有报告目录 | 7 / 13 / 13 / 20 / 31 文件，**数量全部不变** |
| 后台进程 | 8000 与 5173 均已释放，无残留 vite 进程 |

前后快照：`protection_snapshot_before.json` / `protection_snapshot_after.json`
（自动比对通过）。

---

## 9. 未解决的限制

1. **触发率仍低**（validation 四类 B1 约 12/2,079 ≈ 0.58%），页面验收中
   只有特定图片会展示候选区。这是既定的保守设计，非缺陷。
2. **部分触发样本真实标签在四类之外**（`bull_mastiff`、`kelpie`、
   `rhodesian_ridgeback`）。候选提示表达"模型难以区分"，**不代表候选中
   必有正确答案**——本次页面验证也确认了提示文案已明确这一点。
3. **候选提示不解决 APBT/AmStaff 的真实品种可分性问题**。V2.1 在该两类上
   的 P/R/F1 仍低（见 `reports/v2_1_diagnostics/`）。
4. **页面验收覆盖 4 张图片、2 个开关状态**，不是全量 val 图片的页面巡检；
   批量行为以 U5.2 的 160 项 API 验收与 U5.1 的 2,079 张离线评估为准。
5. **本次修复的文案在 U5.2 阶段未被发现**，说明此前的组件测试未断言
   "图例数字与实际候选数一致"这一项；本次已把该断言加入页面验收脚本，
   但**尚未加入 `frontend/tests/` 的单元测试**（如需固化，建议后续补充）。
6. `runtime/` 目录为**临时验收产物**（临时 SQLite + 上传副本），
   按"不清理工作区"要求保留现场；它不是正式数据路径，可人工确认后删除。

---

## 10. 本轮改动清单

| 文件 | 类型 | 内容 |
|---|---|---|
| `frontend/src/components/PredictionResult.vue` | 修改 | 图例"三个候选"→ 动态 `{{ candidateCount }}个候选`；新增 `candidateCount` computed |
| `scripts/run_four_breed_backend.py` | 新增 | 注入式隔离后端启动器（不改生产默认值） |
| `scripts/page_accept_four_breed.mjs` | 新增 | Playwright 页面验收脚本（5 场景、34 项断言、截图） |
| `scripts/reconcile_u5_2_numbers.py` | 新增 | 只读复算 U5.2 四个基础数字 |
| 本目录 9 个文件 | 新增 | 见目录列表 |

**未修改**：`backend/app/config.py`、`backend/app/main.py`、`backend/app/services/candidate_group.py`、
`ml/*`、`artifacts/*`、`data/*`、任何既有报告。

---

## 11. Git 状态（未提交、未清理）

本轮**未执行 `git commit`**、未 `git add`、未 `reset --hard`、未 `git clean`、
未清理工作区。开始前状态见 `git_status_before.txt`。

---

**验收完成并停止，等待人工审核。未自动启用候选功能、未切换正式模型、未训练 V2.2。**
