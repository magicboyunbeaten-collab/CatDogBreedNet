# U6.7：exp06 分辨率与 collie-pair 完善 + Git 交付同步 — 验收报告

> **结论：exp06 的 256 分辨率链路经核查完整（无需改动）；collie-pair 在不回退模型的
> 前提下恢复可用** —— 判定量由"绝对分差"改为**组内相对份额**，阈值 `0.20` 由
> validation 网格按预设规则选出，触发 **3/2079（0.1443%）**，真实标签全部在组内、
> **组外误触发 0 张**；四类组一行未改。
>
> **Git 状态需分开看**：阶段 A 的 3 个既有提交**已推送并回读确认**（远端曾到达
> `2e83c5f`）；阶段 C 新增的 2 个提交（`6588fe0`、`bb931a0`）**推送失败（网络不可达，
> 三次尝试）**，状态为**待重试**，**尚未在远端**。详见 §6.1。
>
> 生成时间：2026-10-21
> 默认模型：`artifacts/v2_2_border_collie_exp06_resolution256_lowlr_seed42/best_model.pth`
> 版本：`v2_2_exp06_resolution256_lowlr_seed42`，`image_size=256`，136 类

---

## 0. 三层表述纪律（必须同时出现，缺一即误导）

1. **整体模型指标**：本轮**未改动任何模型权重**。exp06 的 validation macro-F1
   仍为 `0.814947`（V2.1 基线 `0.803806`），与 U6.6 一致。
2. **候选提示策略效果**：collie-pair 由"永久休眠（0 触发）"变为"3 张触发、
   组外误触发 0"，这是**提示可用性**的改善，**不是**分类准确率的改善。
   候选组只是附加信息，不替换 Top-1/Top-K，也不参与历史记录写入。
3. **泛化能力尚未验证**：新阈值 `share ≥ 0.20` 是在**同一 validation** 上选出的，
   因此该 validation 结果**不能再被当作独立的无偏泛化估计**；test split
   访问次数为 **0**，泛化能力未经检验。

---

## 1. 阶段 A：Git 交付同步

| 步骤 | 结果 |
|---|---|
| 只读核查 | HEAD `2e83c5f`、分支 `master`、`M=0`、暂存区空、`??`=88（含本任务单） |
| `git ls-remote origin refs/heads/master` | **`ca86b0b`**，`exit=0`（实际网络读取，非本地缓存 ref） |
| 分支关系 | 远端是本地**祖先**，本地领先 **3 个提交** → **可快进** |
| 提交审查 | 3 个提交共 **10 个文件**，全部为 `backend/`、`ml/`、`tests/`、`*.bat`；**无 `.pth`/DB/数据/uploads/缓存/密钥**；**无机器专属绝对路径** |
| 推送 | `git push origin HEAD:master` → `ca86b0b..2e83c5f  HEAD -> master`，**exit 0**（普通快进，非 force） |
| 回读复核 | `git ls-remote` 返回 **`2e83c5f`** == 本地 HEAD ✅ |

**A 段结论：远端 SHA 与本地 HEAD 完全一致，同步完成。**

### 1.1 阶段 C 产生的新提交（**A 段推送不含这些**）

见 §6。新提交在 A 段推送**之后**产生，需**单独审查并再次推送**；
在完成第二次推送并回读确认之前，**不得声称它们已在远端**。

---

## 2. 阶段 B：256 分辨率链路核查

**结论：链路完整（21/21 项通过），未做任何代码改动。**

| 环节 | 实测 |
|---|---|
| `config.py` 默认值 | `DEFAULT_IMAGE_SIZE = 256`、`Settings.image_size = 256` |
| `CATDOG_IMAGE_SIZE` 解析 | 设为 `224` 时 `Settings.from_env().image_size == 224`；清除后默认仍 `256` |
| `main.py` lifespan | `image_size=settings.image_size` 传入 `PredictorService` |
| `services/predictor.py` | 形参 `image_size`，透传给 `Predictor`，写入 `self.image_size`，日志含 `image_size=%d` |
| `ml/predictor.py` | `predict_pil` 用 `build_transforms(train=False, image_size=self.image_size)` |
| **transform 实际输出** | `256 → (3, 256, 256)`、`224 → (3, 224, 224)` —— 分辨率确实生效，不是只改配置 |
| `schemas.py` / health | `HealthResponse.model_version` 存在，运行中返回实际版本 |
| 两个 `.bat` | **均不设置任何 `CATDOG_*`**；默认目录指向 exp06；回退提示含 `CATDOG_IMAGE_SIZE` |
| 回退说明 | `config.py` 同时给出 `CATDOG_WEIGHTS_PATH` / `CATDOG_CLASS_NAMES_PATH` / `CATDOG_IMAGE_SIZE` |

**默认启动冒烟**（仅重定向 DB/uploads，其余全默认）：

```json
{"status":"ok","model_loaded":true,"num_classes":136,
 "model_weights":"best_model.pth",
 "model_version":"v2_2_exp06_resolution256_lowlr_seed42",
 "model_error":null,"version":"1.0.0"}
```

```
INFO: class mapping verified against class_names.json (136 classes)
INFO: model ready: version=v2_2_exp06_resolution256_lowlr_seed42 arch=resnet18 classes=136 device=cuda image_size=256 (weights: best_model.pth)
```

---

## 3. 阶段 C：诊断（先算后改）

### 3.1 归因：不是前置条件，是绝对阈值

| 统计（exp06 @256，validation 2079 张） | 值 |
|---|---:|
| 真实属于两类的图 | 31 |
| 其中 **Top-1 在组内** | **29** |
| 其中 Top-1 落在组外（true→pred） | 2（border_collie→bernese 0.664；collie→pembroke 0.928） |
| Top-1 在组内、真实标签**在组外** | 7 |
| **原策略（mass≥0.30 且 margin≤0.30）触发** | **0** |

→ 29/31 的 Top-1 已经落在组内，**前置条件没有挡住**；真正的原因是
**绝对分差 `abs(p_collie − p_border)` 随模型整体变果断而整体抬升**：
exp06 下 31 张目标类的绝对分差**最小也有 0.3281**，全部 > 0.30。

**两类互相错分**：`collie` 16 张中 11 张正确（68.75%）、4 张被判成 `border_collie`；
`border_collie` 15 张中 13 张正确（86.67%）、1 张被判成 `collie`。

### 3.2 关键证据：mass 挡不住，share 才挡得住

那 7 张"Top-1 在组内但真实在组外"的图（cardigan / papillon /
english_springer / shetland_sheepdog ×3 / bernese_mountain_dog）
**pair_mass 高达 0.6544–0.9961，全部通过 0.30 门槛**；
但它们的 `share` 最高只有 **0.0841**。→ **只看 mass 会给这些图错误地加上
"两类难以区分"的提示；起拦截作用的是 share。**

### 3.3 组内相对份额定义

```
pair_mass  = p_collie + p_border_collie
share      = min(p_collie, p_border_collie) / pair_mass
```

`share` 是**组内相对比例**，与 softmax 的绝对尺度无关。同一批图片在两个模型下
`share` 稳定、绝对分差却整体漂移：

| 图片 | V2.1 margin / share | exp06 margin / share |
|---|---|---|
| `n02106166_416` | 0.2017 / 39.9% | 0.4076 / **29.6%** |
| `n02106166_549` | 0.2078 / 39.6% | 0.5788 / **20.6%** |
| `n02106166_884` | 0.2525 / 27.8% | 0.3281 / **24.3%** |

### 3.4 阈值选择（规则在看数据前已写定）

**规则**：覆盖 v1 曾触发的 3 张图 + 组外误触发 0 + 总触发率 < 1%，在满足者中取**最大** θ。

| θ | 触发数 | 触发率 | 真实在组内 | **组外误触发** | 真实标签分布 |
|---:|---:|---:|---:|---:|---|
| 0.10 | 6 | 0.2886% | 6 | **0** | border_collie ×6 |
| 0.15 | **3** | 0.1443% | 3 | **0** | border_collie ×3 |
| **0.20** | **3** | **0.1443%** | **3** | **0** | border_collie ×3 |
| 0.25 | 1 | 0.0481% | 1 | 0 | border_collie ×1（覆盖不足） |
| 0.30 / 0.35 / 0.40 | 0 | 0 | — | — | — |

θ=0.25 只剩 1 张 → 不满足覆盖；**θ=0.20 是满足全部条件的最大值**，故取 **0.20**。

**间隔证据**：目标类 share 降序为 `0.2962 / 0.2430 / 0.2058`，第 4 名骤降至
**0.1119**（约 1.84 倍间隔），阈值落在间隔正中偏左，不是"贴着数据剪裁"。

**触发样本（θ=0.20 全部 3 张）**：

| 图片 | 真实标签 | Top-1 | mass | margin | share |
|---|---|---|---|---:|---:|---:|
| `border_collie/n02106166_416.jpg` | border_collie | border_collie | 0.9952 | 0.4056 | 0.2962 |
| `border_collie/n02106166_884.jpg` | border_collie | border_collie | 0.6383 | 0.3281 | 0.2430 |
| `border_collie/n02106166_549.jpg` | border_collie | border_collie | 0.9836 | 0.5788 | 0.2058 |

> **诚实说明**：3 张触发图全部是真实 `border_collie`；**真实 `collie` 从不触发**
> （其 share 最高仅 0.0912）。这与 v1 的不对称性一致——模型对 `collie` 很少犹豫。
> 该不对称是数据事实，不是实现缺陷，但它意味着**提示对"柯利被误判"这一方向没有帮助**。

---

## 4. 改动

| 文件 | 改动 |
|---|---|
| `backend/app/services/candidate_group.py` | 新增 `COLLIE_PAIR_SHARE_THRESHOLD = 0.20`；`build_collie_pair_group` 的 `margin_threshold` 参数改为 `share_threshold`；判定改为 `pair_mass ≥ 0.30 且 pair_share ≥ 0.20`；`COLLIE_PAIR_VERSION` 升为 `val-2026-10-21-collie-pair-v2`；返回值新增 `group_share`，保留 `group_margin` 作信息性字段；删除 v1 的 `COLLIE_PAIR_MARGIN_THRESHOLD` |
| `backend/app/schemas.py` | `CandidateGroupInfo` 新增可选 `group_share: float \| None = None`（默认 None，旧响应兼容） |
| `tests/test_collie_pair_candidate.py` | 触发/不触发用例改写为 share 语义；新增"高 mass 低 share 不触发"、"share 边界包含"、"mass 边界包含"、"group_share 字段"断言；版本断言升 v2；覆盖点一个未删 |
| `tests/test_candidate_group.py` | 仅把导入的常量名换成 `COLLIE_PAIR_SHARE_THRESHOLD`；**四类组的 margin 用例全部保持原样** |

**未改动**：`PredictionResult.vue`、`four-breed-bully` 的成员/阈值/版本/逻辑、
模型权重、`ml/predictor.py`、`config.py`、两个 `.bat`（B 段核查确认无需改）。

---

## 5. 验收

### 5.1 回归

| 命令 | 退出码 | 结果 |
|---|---:|---|
| `pytest tests/test_collie_pair_candidate.py tests/test_candidate_group.py -q` | 0 | **74 passed**（定向） |
| `pytest tests/ -q` | 0 | **281 passed**（U6.6 为 278，**+3** 新增） |
| `cd frontend; npm test` | 0 | **85 passed / 12 files**（无前端改动，无回归） |
| `cd frontend; npm run build` | 0 | **成功 874 ms** |

### 5.2 隔离默认启动冒烟（4 个样本，全部 PASS）

| 样本 | Top-1 | triggered | group_id / 版本 | mass / share | 得分和 |
|---|---|---|---:|---|---:|
| `border_collie/n02106166_416.jpg` | border_collie 0.7014 | **True** | `collie-pair` / **v2** | 0.9952 / **0.2952** | **100.0** |
| `american_pit_bull_terrier_132.jpg` | AmStaff 0.5768 | **True** | `four-breed-bully` / b1 | 0.9985 / — | **100.0** |
| `beagle/beagle_101.jpg` | beagle 0.9988 | False | — | — | — |
| `border_collie/n02106166_204.jpg` | border_collie 0.6856 | **False** | `collie-pair` / v2 | share 0.1119 < 0.20 | — |

每个样本逐项通过：HTTP 200、Top-K 仍 3 行、响应不含 `probabilities`、
`group.top1_breed == predictions[0].breed`、`top1_confidence` 一致、
触发时组内得分和 ≈100 且等于 `original_confidence / group_mass × 100`、
collie-pair 触发样本带 v2 版本与 `group_share` 字段。
**候选提示只追加信息，原始 Top-1/Top-K/分数完全保留。**

不触发样本的 `reason` 也为运维给出了可读理由：
`组内相对份额 0.1119 < 0.20，模型已在这两个品种之间做出明确偏好`。

### 5.3 四类组零回归

| 检查 | 结果 |
|---|---|
| `CANDIDATE_GROUP` 成员 | 未变（APBT / AmStaff / SBT / American Bulldog） |
| `MASS_THRESHOLD` / `MARGIN_THRESHOLD` | 0.30 / 0.40 **未变** |
| `THRESHOLD_VERSION` | `val-2026-10-19-four-breed-b1` **未变** |
| 代表样本行为 | 触发、4 个候选、得分和 100、`group_id=four-breed-bully` 与改动前一致 |
| `group_share` | 四类组返回中**不出现**该字段（保持原契约） |
| reason 文案 | 四类组仍用"组内分差 … ≤ 0.40"，未被两类组的改动影响 |

**触发数量差异说明**：本轮**未改模型**，四类组判定未改，因此其在同一批样本上的
触发结果与 U6.6 完全一致（U6.6 记录 2079 张中 7 张触发）。

### 5.4 保护核验（16/16 通过）

V1.1 / V2.1 / exp06 三份 `.pth` SHA256 **全部未变**；
V2.1 与 exp06 的 `class_names.json` **字节一致**；
五个数据目录已记录；正式 DB **142 条 + integrity ok**；`uploads` **142**；
默认模型仍 exp06、`image_size=256`、候选开关 True；
**test split 访问次数 = 0**。

---

## 6. Git 最终状态

| 项目 | 值 |
|---|---|
| A 段推送前远端 | `ca86b0b7bdbb1530f1c96896c3316e48a81f9868` |
| A 段推送后远端 / 本地 HEAD | `2e83c5f6894baac7b7228295ba5f5caf931da7d3`（**已同步**） |
| A 段推送的提交 | `96c5511`（5 文件）、`a03ddb3`（2 文件）、`2e83c5f`（3 文件） |

### 6.1 阶段 C 的新提交与第二次推送

| # | commit | message | 文件数 |
|---|---|---|---:|
| 1 | `6588fe0` | Decide collie-pair on group-relative share instead of absolute margin | 2 |
| 2 | `bb931a0` | Cover the collie-pair share rule with tests | 2 |

- 两组均用 `git add -- <精确路径>`，逐组核对 `git diff --cached --name-status`
  与清单集合相等（2/2、2/2），扫描无本地绝对路径、无密钥、无产物路径。
- 提交后 `git status --short` 中 `M` = **0**，暂存区为空；提交后重跑
  `pytest tests/ -q` → **281 passed**，与提交前一致。

**⚠ 第二次推送失败，状态为"待重试"，这 2 个提交尚未在远端。**

| 项目 | 值 |
|---|---|
| 推送前远端实际 SHA | `2e83c5f6894baac7b7228295ba5f5caf931da7d3`（`ls-remote`，exit 0，**是本地祖先**，可快进） |
| 本地 HEAD | `bb931a05cd4b43c4679d362643febc74fb2ff473` |
| 尝试次数 | **3 次**（间隔递增至 20s），全部失败 |
| 错误原文 | `fatal: unable to access '…CatDogBreedNet.git/': Recv failure: Connection was reset`<br>`fatal: … Failed to connect to github.com:443 after 21090 ms: Could not connect to server` |
| 最终 `ls-remote` 复核 | 同样因网络失败（exit 128），**无法读取远端** |
| 结论 | **远端尚未包含 `6588fe0` / `bb931a0`**；本地 `master` 领先 2 个提交，等待网络恢复后重试普通推送 |

**未执行**：force push、`fetch`/`pull`/`rebase`、任何破坏性操作。
网络恢复后需要的动作只有一条（普通快进）：

```powershell
git push origin HEAD:master
git ls-remote origin refs/heads/master   # 应返回 bb931a0…
```

> 说明：A 段那 3 个提交（`96c5511` / `a03ddb3` / `2e83c5f`）在此次网络故障**之前**
> 已推送成功并回读确认，因此它们**确实**在远端；本次失败的只是阶段 C 的 2 个新提交。
> 二者不可混为一谈。

---

## 7. 限制与遗留

1. **validation 双重角色**：阈值由 validation 选出，同一 validation 的 3/2079
   触发率**不能**当作无偏泛化估计；test split 未使用（访问 0 次），
   真实数据上的触发率未知。
2. **提示方向不对称**：3 张触发图全为真实 `border_collie`；真实 `collie`
   （share 最高 0.0912）从不触发。因此本策略对"柯利牧羊犬被误判"方向无帮助。
3. **样本量极小**：31 张目标类、3 张触发；任一图片变化都可能改变触发集合。
4. **触发 ≠ 纠错**：3 张触发图中 Top-1 本来就是 `border_collie`（正确），
   提示的价值在于"暴露两类的相对接近程度"，**不改变分类结果**；
   不得表述为提升了准确率。
5. **`group_margin` 语义变化**：v2 起它只作信息性字段，不再是 collie-pair 的
   判据；依赖该字段做判定的外部消费者需改用 `group_share`。
6. **模型版本仍依赖 `artifacts/`**（`model_version.json` 与 `.pth` 同处，不入库），
   干净克隆中 health 的 `model_version` 为 `null`。

---

## 8. 交付物

| 文件 | 内容 |
|---|---|
| `acceptance_report.md` | 本报告 |
| `collie_pair_validation.json` | 全量统计、原/新策略逐档比较、触发样本、阈值依据、`share` 定义 |
| `runtime_smoke.json` | health 全字段、启动日志身份行、4 个样本逐项断言 |
| `protection_summary.json` | 权重/映射/数据/DB/uploads 核验、两套策略当前参数 |
| `chain_check.json` | 阶段 B 的 21 项链路核查明细 |
| `raw_eval/val_pair_256.csv` | 2079 张逐图 `p_collie` / `p_border_collie` / `pair_mass` / `pair_margin` / `pair_share` |

**只读命令清单**：`git rev-parse`、`branch`、`status`、`diff`、`log`、`ls-remote`、
`merge-base`；`git push origin HEAD:master`（A 段，快进，非 force）。
