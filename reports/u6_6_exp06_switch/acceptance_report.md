# U6.6：exp06 候选切换与毕业设计交付准备 — 验收报告

> **结论：exp06 已切换为正式默认模型。** 同口径 Macro-F1 由 `0.803806` 升至
> `0.814947`（**+0.011141**），三 seed 均值 `0.815196` 且 3/3 高于基线；
> 权重兼容性、类别映射一致性、推理分辨率、三项回归与隔离冒烟均已通过。
>
> 生成时间：2026-10-21
> 切换前默认：V2.1 `artifacts/v2_1_136classes_seed42/best_model.pth`（224 分辨率）
> **切换后默认：exp06 `artifacts/v2_2_border_collie_exp06_resolution256_lowlr_seed42/best_model.pth`（256 分辨率）**
> 实际运行版本标识：**`v2_2_exp06_resolution256_lowlr_seed42`**

---

## 0. 三层表述纪律（先讲清，避免误导）

1. **整体指标更好**：同一 validation split（`data/v2_processed/val`，n=2079）、同一
   macro-F1 口径下，exp06 `0.814947` > V2.1 `0.803806`，**+0.011141**。
2. **不等于所有类别都更好**：136 类中 **70 类改善、25 类持平、41 类退化**，
   其中 **7 类 F1 下降超过 0.10**（见 §3）。验证集每类仅约 10–23 张，
   单张样本即可造成数个百分点波动。
3. **边牧专项未达原冻结目标**：`collie` F1 三 seed 均值 `0.6455` 未稳定越过
   `+0.10`，双向错误未降到 ≤4。本次采纳的理由是**用户已明确的"整体 Macro-F1 优先"规则**，
   **不是**因为边牧专项达标；不得表述为"边牧已优化成功"或"所有错误已解决"。

---

## 1. 决策依据

| 判据 | 要求 | 实测 | 结论 |
|---|---|---|---|
| 同口径 Macro-F1 优于基线 | `exp06 > baseline` | 0.814947 > 0.803806（+0.011141） | **通过** |
| 权重兼容 | resnet18 / 136 类 / 可被现有服务加载 | arch=resnet18、num_classes=136、`fc.weight` (136,512)、122 个张量 | **通过** |
| 类别映射一致 | 分类头顺序与既有 136 类映射完全一致 | checkpoint `class_names` 与 `class_names.json` **逐项相同**；两份 JSON **字节相同**（SHA256 均为 `216dae77…a07505ad`） | **通过** |
| 推理预处理可用 | 现有服务能按训练分辨率预处理 | 原先**不满足**（写死 224），本次补齐为可配置 256 | **修复后通过** |
| 三 seed 稳定 | 不只看单 seed | 0.814947 / 0.812337 / 0.818305，均值 0.815196（sd 0.002442），**3/3 高于基线** | **通过** |

### 1.1 关键发现：不补分辨率就"换了反而更差"

exp06 训练与 U6.1 评估均为 **256**，而原推理链路 `ml/predictor.py` 固定使用
`build_transforms(train=False)` 的默认 **224**。本次在 validation 上做了最小必要复评：

| 配置 | Accuracy | Macro-F1 | 相对 V2.1 基线 |
|---|---:|---:|---:|
| V2.1 @224（冻结基线） | 0.797018 | 0.803806 | — |
| **exp06 @256**（训练分辨率） | 0.809524 | **0.814947** | **+0.011141** |
| exp06 @224（未修分辨率时） | 0.793651 | 0.800995 | **−0.002811** |

> **若只改权重路径而不打通 `image_size`，exp06 的实际效果会低于基线**。
> 224 预处理造成的损失约 **0.013952**。这是本次把分辨率贯通当作切换前置条件
> （而非可选项）的直接证据。exp06@256 与 U6.1 记录的 `0.814947` 在 CSV 6 位小数
> 精度内完全一致（实际 0.8149474329…）。

---

## 2. 修改文件（10 个）

| # | 文件 | 改动 |
|---:|---|---|
| 1 | `backend/app/config.py` | `DEFAULT_MODEL_DIR` → exp06 目录；新增 `DEFAULT_CLASS_NAMES_PATH`（继续指向既有 136 类映射）与 `DEFAULT_IMAGE_SIZE = 256`；`Settings` 新增 `image_size` 字段，`from_env` 用 `_env_int("IMAGE_SIZE", 256)` |
| 2 | `ml/predictor.py` | `Predictor.__init__` 新增 `image_size: int = IMAGE_SIZE`（默认 224，向后兼容）；`predict_pil` 改用 `build_transforms(train=False, image_size=self.image_size)` |
| 3 | `backend/app/services/predictor.py` | `PredictorService.__init__` 新增 `image_size` 并透传给 `Predictor`；启动日志追加 `image_size=%d` |
| 4 | `backend/app/main.py` | lifespan 透传 `settings.image_size`；`/api/health` 返回 `model_version` |
| 5 | `backend/app/schemas.py` | `HealthResponse` 新增可选 `model_version: str \| None = None` |
| 6 | `启动后端.bat` | `MODEL_DIR` → exp06；新增 `CLASS_NAMES_FILE`（指向既有 136 类映射）；错误提示改为 exp06，回退提示**同时给出 V2.1 与 V1.1 两组命令（含 `CATDOG_IMAGE_SIZE=224`）** |
| 7 | `启动系统.bat` | 同上 |
| 8 | `tests/test_candidate_group.py` | `test_settings_default_model_is_v2_1` → `..._is_exp06`（断言目录名 / `image_size==256` / 映射来源 / 两份映射字节一致）；新增 `image_size` 环境变量覆盖、V2.1 回退可解析两个用例；强化 V1.1 文件存在用例 |
| 9 | `tests/test_predictor_service.py` | 新增 4 个用例：`image_size` 透传、默认 224、启动日志含 `image_size=`、`version_id` 透出、无版本文件时为 `None` |
| 10 | `tests/test_api.py` | 新增 3 个用例：health 返回 `model_version`、缺失时为 `None`、旧响应兼容 |

**新增文件（不入库）**：`artifacts/v2_2_border_collie_exp06_resolution256_lowlr_seed42/model_version.json`
——沿用项目既有版本机制（`read_model_version` 读权重同目录的该文件），
`version_id = v2_2_exp06_resolution256_lowlr_seed42`，含 checkpoint/映射 SHA256、
`image_size=256`、`best_epoch=22`、`best_val_macro_f1`、`init_from`（指向 V2.1、
`head_transferred=true`）。**仅新增，未修改 V2.1 任何文件、未改动任何 `.pth`。**

**未改动**：`candidate_group.py`（成员/阈值/版本**一行未动**）、前端代码、`ml/train.py`、
`ml/dataset.py`、`ml/config.py::IMAGE_SIZE`（保持 224，作为库层默认值）。

---

## 3. 类别级代价（必须呈现）

exp06 @256 相对 V2.1，**7 个类别 F1 下降 > 0.10**：

| 类别 | support | V2.1 F1 | exp06 F1 | Δ |
|---|---:|---:|---:|---:|
| `standard_schnauzer` | 16 | 0.5333 | 0.3571 | **−0.1762** |
| `bluetick` | 17 | 0.8750 | 0.7333 | **−0.1417** |
| `miniature_pinscher` | 10 | 0.6364 | 0.5000 | **−0.1364** |
| `eskimo_dog` | 15 | 0.3571 | 0.2400 | **−0.1171** |
| `miniature_schnauzer` | 16 | 0.6000 | 0.4848 | **−0.1152** |
| `appenzeller` | 15 | 0.6667 | 0.5517 | **−0.1149** |
| `Ragdoll` | 10 | 0.9091 | 0.8000 | **−0.1091** |

整体分布：**改善 70 / 持平 25 / 退化 41**（合计 136）。

> **口径限制**：这些类别在 validation 中仅 10–17 张，1 张样本即可造成约 6 个百分点的
> F1 波动。上表用于**提示风险**，不作为取舍依据，也不代表测试集上必然同样退化。

**边牧两类**（专项目标）：`collie` F1 0.7097（seed42，+0.1215）、三 seed 均值 0.6455
（sd 0.0458）；`border_collie` 0.7222、均值 0.6910。**种子间波动大，未达原冻结标准
（`collie ≥ 0.6882` 且三 seed 稳定、双向错误 ≤4）。**

---

## 4. 测试结果

| 命令 | 退出码 | 结果 |
|---|---:|---|
| `.venv\Scripts\python.exe -m pytest tests/ -q` | **0** | **278 passed**（切换前 268，**+10** 新增用例） |
| `cd frontend; npm test` | **0** | **85 passed / 12 files**（无前端改动，无回归） |
| `cd frontend; npm run build` | **0** | **成功 1.80s** |

受影响三组单独运行：`tests/test_api.py` + `test_predictor_service.py` +
`test_candidate_group.py` → **111 passed**。

---

## 5. 默认启动冒烟（隔离环境）

**构造方式**：`python -m uvicorn backend.app.main:app --port 8000`，仅设置
`CATDOG_DB_PATH` / `CATDOG_UPLOAD_DIR` 指向 `reports/u6_6_exp06_switch/runtime/`；
**未设置** `CATDOG_WEIGHTS_PATH` / `CATDOG_CLASS_NAMES_PATH` / `CATDOG_IMAGE_SIZE` /
`CATDOG_CANDIDATE_GROUP_ENABLED` → 验证的是 `config.py` 默认值本身。

### 5.1 `/api/health`

```json
{
  "status": "ok",
  "model_loaded": true,
  "num_classes": 136,
  "model_weights": "best_model.pth",
  "model_version": "v2_2_exp06_resolution256_lowlr_seed42",
  "model_error": null,
  "version": "1.0.0"
}
```

**启动日志**：

```
INFO: database ready: app.db
INFO: class mapping verified against class_names.json (136 classes)
INFO: model ready: version=v2_2_exp06_resolution256_lowlr_seed42 arch=resnet18 classes=136 device=cuda image_size=256 (weights: best_model.pth)
```

> `model_weights` 只给文件名 `best_model.pth`，V1.1/V2.1/exp06 **三者同名**，
> 单凭它无法判断版本；现在 `/api/health.model_version` 可以直接回答这个问题。

### 5.2 三类样本

| 用途 | 样本 | Top-1 | triggered | group_id | 得分和 |
|---|---|---|---|---:|---:|
| collie-pair 已知触发（V2.1 口径） | `border_collie/n02106166_416.jpg` | border_collie 0.7014 | **False** | `collie-pair` | — |
| four-breed 已知触发 | `american_pit_bull_terrier_132.jpg` | AmStaff 0.5768 | **True** | `four-breed-bully` | **100.0** |
| 非目标对照 | `beagle/beagle_101.jpg` | beagle 0.9988 | False | `four-breed-bully` | — |

**结构性不变量（3/3 全部通过）**：HTTP 200、Top-K 仍 3 行、响应不含 `probabilities`、
`candidate_group.top1_breed == predictions[0].breed`、`top1_confidence` 一致、
触发时组内得分和 ≈ 100 且等于 `original_confidence / group_mass × 100`。
→ **候选提示只追加信息，未替换原始 Top-1、Top-K 与原始分数。**

### 5.3 ⚠ 必须报告的发现：exp06 下 collie-pair 不再触发

| 检查 | 结果 |
|---|---|
| 31 张 collie / border_collie validation 图 | **0 张触发** |
| 其中最小 margin | **0.330302**（`border_collie/n02106166_884.jpg`），阈值 0.30 |
| 全量 2079 张 validation | **collie-pair 触发 0 张**；four-breed-bully 触发 **7 张**（V2.1 时为 10 张） |

**成因（有数据）**：exp06 在这两类上明显更果断。V2.1 下触发的三张图
`(mass, margin)` 为 `(0.9992, 0.2017)`、`(0.9987, 0.2078)`、`(0.5689, 0.2525)`；
exp06 下同一批图变为 `0.4076`、`0.5794`、`0.3303`，**均越过 0.30 阈值**。

**处理原则**：**未放宽任何阈值**（`COLLIE_PAIR_MARGIN_THRESHOLD` 一行未动）。
按任务要求不得为凑出触发而调阈值或编造样本，因此：

- 在 exp06 默认配置下，**collie-pair 候选区处于休眠状态**，两套候选里只有
  `four-breed-bully` 会在真实样本上出现；
- 该策略的**实现未被破坏**——15 个 collie-pair 单测全部通过，且在 **V2.1 回退配置**下
  仍按 U6.3 记录逐位一致地触发（见 §5.4）。

### 5.4 回退路径验证（附带完成）

以 `CATDOG_WEIGHTS_PATH`/`CATDOG_CLASS_NAMES_PATH` 指向 V2.1、`CATDOG_IMAGE_SIZE=224`、
隔离存储起服务：

| 检查 | 结果 |
|---|---|
| health `model_version` | `v2_1_136classes_candidate` |
| 启动日志 | `model ready: version=v2_1_136classes_candidate ... image_size=224` |
| collie-pair 样本 `n02106166_416.jpg` | `triggered=True`、`group_id=collie-pair`、mass 0.999177、margin 0.201679、得分 60.0923 / 39.9077、和 100.0 —— **与 U6.3 记录逐位一致** |

→ 回退只需三个环境变量，**无需改代码或移动任何文件**；也证明 exp06 下不触发
来自"模型更果断"，而非"候选策略被改坏"。

### 5.5 进程与存储

| 项目 | 结果 |
|---|---|
| 服务进程 | 已停止，端口 8000 **已释放** |
| 隔离存储 | `reports/u6_6_exp06_switch/runtime/`（默认配置）、`runtime_v21/`（回退验证），**保留作证据，未清理** |
| 正式 `data/app.db` | **142 条**、`integrity ok` —— **未被写入** |
| 正式 `uploads/` | **142 文件** —— **未被写入** |

---

## 6. 保护核验（15/15 通过）

| 检查项 | 结果 |
|---|---|
| V1.1 `artifacts/best_model.pth` | `89ef468f…b1a256` **未变** |
| V2.1 `best_model.pth` | `423e218a…821e1` **未变** |
| exp06 `best_model.pth` | `a7560f4e…ca6c8e` **未变** |
| V2.1 `class_names.json` / `model_version.json` / `experiment_config.json` | **原样未改** |
| exp06 与 V2.1 的 `class_names.json` | **字节一致**（证明未复制/重写映射） |
| 五个数据目录 | 文件数/字节已记录，未变 |
| 正式 DB / uploads | 142 / 142，未变 |
| 默认 `weights_path` | 指向 exp06 ✅ |
| 默认 `class_names_path` | 仍指向 `v2_1_136classes_seed42` ✅ |
| 默认 `image_size` | **256** ✅ |
| 默认 `candidate_group_enabled` | **True** ✅ |

---

## 7. 回退办法

**切回 V2.1（136 类，224 分辨率）**：

```powershell
set CATDOG_WEIGHTS_PATH=E:\CatDogBreedNet\artifacts\v2_1_136classes_seed42\best_model.pth
set CATDOG_CLASS_NAMES_PATH=E:\CatDogBreedNet\artifacts\v2_1_136classes_seed42\class_names.json
set CATDOG_IMAGE_SIZE=224
```

**切回 V1.1（37 类，224 分辨率）**：

```powershell
set CATDOG_WEIGHTS_PATH=E:\CatDogBreedNet\artifacts\best_model.pth
set CATDOG_CLASS_NAMES_PATH=E:\CatDogBreedNet\artifacts\class_names.json
set CATDOG_IMAGE_SIZE=224
```

> **必须同时设置 `CATDOG_IMAGE_SIZE`**：V2.1 与 V1.1 都是 224 训练，
> 只换权重不改分辨率会重复本次量化到的 −0.0139 量级损失。
> 两条回退路径已在 §5.4 实测（V2.1）与单测（V1.1 文件存在 + 路径可解析）中验证。

---

## 8. 遗留风险与限制

1. **collie-pair 在 exp06 下休眠**（§5.3）：全量 validation 0 触发。若毕业设计演示需要
   展示双候选提示，应使用 V2.1 回退配置演示，**或**由人工明确批准调整阈值——
   本任务**未**擅自修改。
2. **7 个类别 F1 下降 > 0.10**（§3），且每类仅 10–17 张验证样本，波动大。
3. **`model_version.json` 与 `.pth` 同样位于 `artifacts/`（不入库）**：干净克隆中
   `/api/health.model_version` 会是 `null`，`version` 与加载能力也依赖模型产物本身。
   **这是既有模型产物管理方式的固有属性，不得表述为"版本信息已纳入版本控制"。**
4. **边牧专项未达原冻结目标**：采纳依据是整体指标规则，不是专项达标。
5. **未做 test split 评估**：本次切换依据 validation，test split 访问次数 **0**。

---

## 9. 毕业设计材料整理要点（下一步，不含新训练）

| 主题 | 要点 |
|---|---|
| 三代模型关系 | V1.1（37 类，224，基线）、V2.1（136 类，224，扩大类目）、**exp06（136 类，256 + 低学习率 warm-start，当前默认）**；exp06 由 V2.1 初始化且 `head_transferred=true` |
| 数据集与划分 | `data/v2_processed`：train 16,655 / val 2,079 / test 5,363（test 全程未使用） |
| 评估方法与指标 | 同 split、同口径 macro-F1；136 类整体 / 原 37 类 / 新增 99 类三组；逐类 F1 delta；三 seed 复核 |
| 候选组策略 | `four-breed-bully`（mass ≥ 0.30 / margin ≤ 0.40，`val-2026-10-19-four-breed-b1`）与 `collie-pair`（mass ≥ 0.30 / margin ≤ 0.30，`val-2026-10-21-collie-pair-v1`）；按原始 Top-1 分发；组内得分为**组内相对得分**，非整体置信度 |
| 策略限制 | exp06 下 collie-pair 休眠；four-breed 触发数由 10 降至 7；不得宣称候选提示提升准确率 |
| 系统演示流程 | 上传图片 → 原始 Top-K → 候选区（若触发）→ 用户选择独立展示（不写库、不覆盖预测）→ 历史记录 |
| 回退步骤 | 见 §7（三环境变量） |
| 局限性与类别级退化 | §3 的 7 类 + 小验证集；未达边牧冻结目标 |

---

## 10. 本任务边界执行情况

| 约束 | 执行情况 |
|---|---|
| 训练新模型 / 超参搜索 / 新实验轮次 | **未执行** |
| 访问 `data/v2_processed/test` | **0 次** |
| 覆盖/删除/移动任何权重 | **未执行**（三份 `.pth` SHA256 均未变） |
| 写正式 `data/app.db` / `uploads/` | **0 次** |
| 修改候选组阈值/成员/版本 | **未执行**（一行未动） |
| 清理 reports/scripts/artifacts/cache/runtime | **未执行** |
| 破坏性 Git 命令（`clean`/`reset`/`checkout`/`restore`/`stash`） | **未执行** |
| `git add .` | **未执行**（分组精确路径） |
| 推送远端 | **未执行** |

---

## 11. 交付物

| 文件 | 内容 |
|---|---|
| `acceptance_report.md` | 本报告 |
| `model_comparison.json` | baseline / exp06 来源、split、口径、Macro-F1、三 seed、224 vs 256 差异、类别级摘要、决策 |
| `runtime_smoke.json` | health 全字段、启动日志身份行、三样本逐项断言、collie-pair 休眠证据、回退验证 |
| `protection_summary.json` | 三份权重与元数据哈希、映射一致性、五数据目录、DB、uploads、默认配置、15 项检查 |
| `runtime/`、`runtime_v21/` | 两套隔离存储，保留作审计证据 |
| `raw_eval/` | 本次 224 vs 256 最小必要复评的 12 个原始 CSV（groups / overall / target / confusion / predictions），供复算 §1.1 的数字 |

> 顶层保持 4 份交付物 + 2 份 git 快照（`git_status_after.txt`、`git_log_after.txt`）+
> `protection_snapshot_before.json`；复评原始数据收在 `raw_eval/` 子目录，避免一次性产物
> 堆在顶层。

---

## 12. Git 提交记录

| # | commit | message | 文件数 |
|---|---|---|---:|
| 1 | `96c5511` | Switch default model to exp06 with matching 256 preprocessing | 5 |
| 2 | `a03ddb3` | Point Windows launchers at the exp06 default model | 2 |
| 3 | `2e83c5f` | Cover exp06 default model, image size and model version in tests | 3 |

- 全部使用 `git add -- <精确路径>`，逐组核对 `git diff --cached --name-status`
  与本组清单集合相等（多出 0 / 缺少 0），并扫描无本地绝对路径 / 无密钥 / 无产物路径。
- **未推送远端**：`origin/master` 仍为 `ca86b0b`，本地 `HEAD` 为 `2e83c5f`，**领先 3 个提交**。
- 提交后 `git status --short` 中 `M` = **0**，暂存区为空；未执行任何
  `reset`/`clean`/`checkout`/`restore`/`stash`/`amend`。
- 提交后重跑 `pytest tests/ -q` → **278 passed**，确认与提交前一致。
