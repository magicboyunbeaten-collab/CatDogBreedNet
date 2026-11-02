# U6.3：建议分组固化计划（**命令尚未执行**）

> **本文件仅为建议文本，等待人工审核后再实际提交。**
> U6.3 任务本身**未执行任何 Git 写操作**（无 `add` / `commit` / `reset` / `clean` / `checkout`）。
> HEAD 仍为 `547c55d v2训练前`。
>
> 生成时间：2026-10-21
> 数据来源：`git_change_inventory.csv`（101 项 = 18 个已跟踪修改 + 83 个未跟踪项）

---

## 0. 前置结论：当前工作区**无法按任务干净切分**

审计发现 **10 个已跟踪文件包含多个任务的混合改动**（详见 `git_change_inventory.csv`
的 `has_mixed_changes=yes` 与 `mixed_change_sources` 列）：

| 文件 | 混合来源 |
|---|---|
| `backend/app/main.py` | U5.5 `class_names_path` 透传 + health `model_weights`；U5.2 候选组接线 |
| `backend/app/services/predictor.py` | U5.5 错配明确失败（含两侧计数）；U5.2 `probabilities` 透传 |
| `frontend/src/components/PredictionResult.vue` | U5.3 图例候选数量动态化；U6.2 `group_id` 渲染 + 副标题 + "不保证候选中一定包含正确品种"；U5.2 既有候选区 |
| `frontend/tests/breedNames.test.js` | U5.5 136 类映射 + 旧 37 兼容；U5.2 候选四类断言 |
| `frontend/tests/historyView.test.js` | U5.5 136 类中文名（`border_collie` 不再回退英文）；U5 既有 |
| `ml/dataset.py` | U6-C `image_size` 参数；U4 既有 `AUGMENT_PRESETS` |
| `ml/train.py` | U6-C pair-only 训练通道 + `--image-size`；U6 warm-start 分类头继承修复；U4 训练扩展 |
| `tests/test_api.py` | U5.5 health `model_weights` 断言；U5.2 候选组响应断言 |
| `tests/test_predictor_service.py` | U5.5 `class_names_path` 与错配失败用例；U5.2 候选组安全返回 |
| `tests/test_train_extensions.py` | U6-C 训练能力；U4 既有 |

**因此本计划不声称"可按任务简单拆分提交"**，而是采用「整文件提交 + 说明」策略：
每个混合文件作为**一个完整单元**提交，commit message 中列明其覆盖的任务范围。

---

## 1. 建议分组

### 分组 A：生产运行必需代码（优先提交）

**理由**：日常启动入口（`启动后端.bat` → `uvicorn backend.app.main:app`）实际加载与
执行这些文件；U6.3 已用运行证据确认其行为（`/api/health` `num_classes=136`、
两套候选策略按 Top-1 分发、关闭开关后原始预测逐位不变）。

**依赖**：`frontend/src/utils/breedNames.js` 被 `PredictionResult.vue` 与
`tests/breedNames.test.js` 依赖；`candidate_group.py` 被 `predict.py`、
`predictor.py` 与两个测试文件依赖。因此本组与分组 B 的测试文件必须**同时或先于**提交，
否则 `pytest` / `npm test` 会因找不到符号而失败。

```bash
# 分组 A：服务端 + 前端生产代码（已跟踪修改 + 新增）
git add backend/app/config.py backend/app/main.py backend/app/schemas.py \
        backend/app/services/predictor.py \
        backend/app/services/candidate_group.py \
        backend/app/routes/predict.py \
        frontend/src/utils/breedNames.js \
        frontend/src/components/PredictionResult.vue
```

### 分组 B：与分组 A 配套的自动化测试

**理由**：锁定 A 组行为；无这些测试则回归无保护。含 10 个混合改动文件中的 6 个
（`test_api.py`、`test_predictor_service.py`、`breedNames.test.js`、
`historyView.test.js`、`predictionResult.test.js` 未跟踪新增、
`predictionResultAcceptance.test.js` 未跟踪新增）。

```bash
git add tests/test_api.py tests/test_predictor_service.py \
        tests/test_candidate_group.py tests/test_collie_pair_candidate.py \
        frontend/tests/breedNames.test.js frontend/tests/historyView.test.js \
        frontend/tests/predictionResult.test.js \
        frontend/tests/predictionResultAcceptance.test.js \
        frontend/tests/colliePairCandidate.test.js
```

### 分组 C：启动脚本（默认入口）

**理由**：`启动后端.bat` / `启动系统.bat` 是日常入口，其 V2.1 路径检查与回退提示
属于"默认启动行为"的一部分。`启动前端.bat` **未修改**，不需提交。

```bash
git add 启动后端.bat 启动系统.bat
```

### 分组 D：训练基础设施（独立成组，**不与候选功能混提**）

**理由**：任务 §3-C2 明确要求"不得把 `ml/train.py`、`tests/test_train_extensions.py`
等先前遗留改动偷偷混入候选功能提交。若它们属于独立训练工具修复，应单独成组。"
本组包含 U6 边牧专项（U6-C）与 U4 的训练能力，以及 warm-start 分类头继承修复——
与线上推理无关，但已被 U6.1/U6 实验使用。

```bash
git add ml/train.py ml/dataset.py ml/u6_pair_training.py \
        tests/test_train_extensions.py
```

### 分组 E：任务单文档（`md/`）

**理由**：项目既有惯例保留任务单（`md/` 下 U5.x/U6.x 任务文件在历次任务中均保留）。
共 10 个文件。**如团队惯例是不提交任务单，整组排除即可**——此处按"保留"给建议，
需人工确认。

```bash
git add md/U5.1_APBT纳入四类候选组离线评估任务.md \
        md/U5.2_方案B1四类相近犬种候选组正式实现任务.md \
        md/U5.4_候选组同图一致性与前端回归测试任务.md \
        md/U5.5_V2.1正式接入与边牧准确率改进计划.md \
        md/U6.1_低学习率纠偏与边牧专项对照实验任务.md \
        md/U6.2_柯利与边境牧羊犬双候选提示实施任务.md \
        md/U6.3_默认启动行为核验与安全固化.md \
        md/V2.1_136类别模型训练任务.md \
        md/V2.1_相近犬种候选提示与边牧复核整合任务.md \
        md/V2.1_误分类诊断与APBT_AmStaff数据审计任务.md \
        md/u6_border_collie_improvement_plan_修订版.md
```

### 分组 F：**不提交**（实验与诊断产物）

**理由**：体积大、与运行代码无关、且含权重/数据库/图片等**禁止入库**的对象
（任务 §保护规则：不得把 `.pth` / 图片 / SQLite / uploads 加入 Git）。

不提交清单（部分示例，完整见 `git_change_inventory.csv` 中
`commit_suggestion=不提交` 的行）：

- `artifacts/` 下全部内容（V1.1 / V2.1 权重、`v2_2_border_collie_exp*` 实验目录）
- `reports/` 下全部内容（`u6_border_collie/`、`u6_1_low_lr/`、`u6_2_collie_pair_candidate/`、
  `u6_3_default_runtime_and_freeze/`、`u5_5_v2_1_integration/`、`v2_1_*` 系列）
- `data/`、`uploads/`、`.cache/`、`frontend/dist/`、`frontend/node_modules/`

**关于 `reports/` 的说明**：任务 §3-C2 要求"不得仅因文件位于 `reports/` 就全部提交或
全部排除，报告是否入库需按项目既有惯例给出建议"。本仓库的 `reports/` 在 git 历史中
**从未被跟踪**（`git log` 无相关记录，且当前全部为未跟踪项），因此建议**维持既有惯例：
不提交 `reports/`**。若团队希望报告入库，应单独决定并考虑体积（`u6_border_collie/`
含 136 类逐图预测 CSV，单文件约 400 KB）。

---

## 2. 依赖关系与提交顺序

```
分组 A（生产代码）
   └─> 分组 B（测试）—— 依赖 A 的符号；必须先提交 A
   └─> 分组 C（启动脚本）—— 依赖 A 的默认配置
分组 D（训练工具）—— 与 A/B/C 无符号依赖，可独立提交
分组 E（任务单）—— 无依赖，可任意顺序
分组 F —— 不提交
```

**建议顺序**：A → B → C → D → E。每组提交后**立即**运行
`.venv\Scripts\python.exe -m pytest tests/ -q` 与 `cd frontend; npm test`
确认无回归，再进入下一组。

---

## 3. 建议的 commit message 模板

分组 A：

```
feat(推理): 接入 V2.1 136 类默认模型与两套相近犬种候选策略

- config.py 新增 DEFAULT_MODEL_DIR 与独立 class_names_path，
  默认指向 V2.1；权重与类名表错配时明确失败（含两侧计数与路径）
- main.py 透传 class_names_path；/api/health 新增 model_weights
- candidate_group.py 支持两套并行策略，按原始 Top-1 分发：
    * four-breed-bully（APBT/AmStaff/SBT/AmBull，mass 0.30/margin 0.40）
    * collie-pair（collie/border_collie，mass 0.30/margin 0.30）
- breedNames.js 扩到 136 条中文映射（旧 37 条原样保留）
- PredictionResult.vue 渲染 group_id，图例动态显示候选数量
  并声明"不保证候选中一定包含正确品种"

运行证据见 reports/u6_3_default_runtime_and_freeze/acceptance_report.md
```

分组 B：`test: 补齐候选策略、136 类映射与配置解析的回归测试`
分组 C：`chore(启动): 启动脚本检查 V2.1 默认模型并附回退提示`
分组 D：`feat(训练): pair-only 颜色扰动/加权采样、image_size 与 warm-start 分类头继承修复`
分组 E：`docs: 归档 U5.x/U6.x 任务单`

---

## 4. 提交前必须核对的事项

1. `git diff --cached --name-status` —— 逐文件确认与上面分组一致；
2. **确认没有任何 `artifacts/`、`data/`、`uploads/`、`.cache/`、`reports/` 路径进入暂存区**；
3. `git status --short` 中 `??` 的未跟踪项是否已按分组 F 排除；
4. 每个混合改动文件是否已在 commit message 中列明覆盖范围；
5. 提交后立即跑回归（见第 2 节）。

---

## 5. 尚未执行的操作

本计划**未执行**任何 `git add` / `git commit` / `git reset` / `git clean` / `checkout`。
工作区保持 U6.3 开始时的原状（HEAD `547c55d`，18 个已跟踪修改 + 83 个未跟踪项）。
