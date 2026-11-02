# U6.4.1：提交前测试结果（硬门禁）

> 执行时间：2026-10-21
> 门禁规则：**三项全部退出码 0 之前，不得执行任何 `git add` / `git commit`。**

---

## 0. 门禁结论

| # | 命令 | 工作目录 | 退出码 | 结果 |
|---:|---|---|---:|---|
| 1 | `.venv\Scripts\python.exe -m pytest tests/ -q` | `E:\CatDogBreedNet` | **0** | **268 passed**, 4 warnings |
| 2 | `npm test` | `E:\CatDogBreedNet\frontend` | **0** | **85 passed / 12 files** |
| 3 | `npm run build` | `E:\CatDogBreedNet\frontend` | **0** | **成功 1.70s** |

**门禁通过 → 允许进入提交阶段。**

---

## 1. 后端全量测试

**命令**：

```powershell
cd E:\CatDogBreedNet
.venv\Scripts\python.exe -m pytest tests/ -q
```

**输出摘要**：

```
268 passed, 4 warnings in 20.74s
PYTEST_EXIT=0
```

| 项目 | 值 |
|---|---|
| 退出码 | **0** |
| 通过 | **268** |
| 失败 / 错误 | 0 |
| 警告 | 4（`PIL.Image.Image.getdata` 弃用提示，既有，与本任务无关） |
| 上一基线（U6.3/U6.4 记录） | 265 passed |
| 增量 | **+3** = 本任务 §2.2 新增的三个用例 |

**新增用例（全部通过）**：

- `test_same_class_count_but_reordered_names_refuses_to_start`
- `test_same_class_count_but_different_name_refuses_to_start`
- `test_same_class_count_mismatch_does_not_start_service`

单独运行该文件确认：`tests/test_predictor_service.py` → **14 passed**（11 既有 + 3 新增）。

**警告明细（既有，非本任务引入）**：

```
tests/test_api.py::test_predict_database_failure_cleans_orphan_upload
  E:\CatDogBreedNet\tests\test_api.py:68: DeprecationWarning:
  Image.Image.getdata is deprecated and will be removed in Pillow 14 (2027-10-15).
  Use get_flattened_data instead.
```

---

## 2. 前端测试

**命令**：

```powershell
cd E:\CatDogBreedNet\frontend
npm test
```

**实际执行方式**：`cmd /c "npm test > <log> 2>&1"` 后台运行后读取日志
（本环境下 PowerShell 直调 `npm` 不稳定，`npx vitest run <单文件>` 会被误判为
需要下载 vitest，故统一走 `npm test`）。

**输出**：

```
> catdog-breed-frontend@1.0.0 test
> vitest run

 RUN  v5.0.4 E:/CatDogBreedNet/frontend
 ✓ tests/breedNames.test.js (8 tests) 11ms
 ✓ tests/fileValidation.test.js (6 tests) 4ms
 ✓ tests/api.test.js (7 tests) 6ms
 ✓ tests/navigation.test.js (6 tests) 5ms
 ✓ tests/http.test.js (5 tests) 2ms
 ✓ tests/imageUploader.test.js (8 tests) 166ms
 ✓ tests/predictionResultAcceptance.test.js (8 tests) 232ms
 ✓ tests/colliePairCandidate.test.js (6 tests) 231ms
 ✓ tests/statsView.test.js (9 tests) 256ms
 ✓ tests/predictionResult.test.js (13 tests) 277ms
 ✓ tests/historyView.test.js (5 tests) 420ms
 ✓ tests/router.test.js (4 tests) 4ms
 Test Files  12 passed (12)
      Tests  85 passed (85)
   Duration  37.14s
```

| 项目 | 值 |
|---|---|
| 退出码 | **0** |
| 测试文件 | **12 passed** |
| 用例 | **85 passed** |
| 失败 | 0 |
| 上一基线 | 85 passed / 12 files |
| 增量 | **0**（本任务只改测试内部的数据来源，未增删用例） |

**关键确认**：`tests/predictionResultAcceptance.test.js` **8 个用例全部通过**，
且改为 inline fixture 后**没有任何断言被放宽**（见 §4 对照）。

---

## 3. 前端生产构建

**命令**：

```powershell
cd E:\CatDogBreedNet\frontend
npm run build
```

**输出**：

```
✓ built in 1.70s
[plugin builtin:vite-reporter]
(!) Some chunks are larger than 500 kB after minification. ...
```

| 项目 | 值 |
|---|---|
| 退出码 | **0** |
| 状态 | **成功 1.70s** |
| 警告 | chunk > 500 kB（既有，来自 Element Plus 等依赖，非本任务引入） |

---

## 4. 两项修复的验收证据

### 4.1 §2.1 让 acceptance 测试自包含

| 检查项 | 结果 | 证据 |
|---|---|---|
| 移除运行时文件读取 | ✅ | 全文已无 `import { readFileSync } from 'node:fs'`、无 `node:url` / `node:path`、无顶层 `readFileSync(...)` |
| 移除对 `reports/` 的运行时依赖 | ✅ | `select-string` 搜索结果中 `reports/` 与 `acceptance_api_responses` **仅出现在文件头注释**（说明改造原因），运行时代码零引用 |
| 8 个场景全部保留 | ✅ | `A`–`H` 共 8 个 `it(...)`，名称与顺序未变 |
| 断言强度未放宽 | ✅ | 见下表逐条对照 |
| 不修改被测组件 | ✅ | `frontend/src/components/PredictionResult.vue` 本轮**零改动**（git diff 为空） |
| 覆盖两个 Top-1 方向 | ✅ | `TRIGGERED_APBT`（Top-1=APBT）与 `TRIGGERED_AMSTAFF`（Top-1=AmStaff） |
| 覆盖两条不触发路径 | ✅ | `CONTROL_NOT_TRIGGERED`（`triggered=false`）与 `SWITCH_OFF`（`candidate_group=null`） |

**断言逐条对照（改造前 → 改造后，完全一致）**：

| 场景 | 断言 | 变化 |
|---|---|---|
| A | `candidates.length === 4`；每个 `breed_zh` 出现在文本 | 无 |
| B | `sum toBeCloseTo(100, 2)`；含「候选组内相对得分」「不是」 | 无 |
| C | `group_score toBeCloseTo(original/group_mass*100, 2)` | 无 |
| D | 含 `Top-1`；含 `(conf*100).toFixed(2)%`；`top1_breed` 相等；`top1_confidence toBeCloseTo(..., 9)` | 无 |
| E | 含「你选择的品种」「模型首选仍为」；`radios.length === 4`；选非首选后含 `breed_zh` 与「未被替换」；props 两处未被修改 | 无 |
| F | 每个 control 都无 `.candidate-block`；文本不含「外观相近的候选品种」 | 无 |
| G | `candidate_group ?? null === null`；无 `.candidate-block` | 无 |
| H | 含「登记品种」「单张图片未必足以可靠区分」；不含「其中必有一个」「一定是」 | 无 |

**fixture 数值保真**：四段响应逐字段复制自 U5.2 隔离验收的真实返回值，
`group_score` / `group_mass` / `group_margin` 均未改动。
两条触发样本的组内得分和分别为 `100.0` 与 `99.99999999999999`（浮点累加），
均满足 `toBeCloseTo(100, 2)`。

**fixture 保持无 `group_id`**：`group_id` 是 U6.2 才加入的字段，被引用的那份真实响应
本来就没有。保持原样既忠实于历史响应，也顺带覆盖「U6.2 之前旧响应」的向后兼容路径
（组件对缺失 `group_id` 有安全兜底）。

### 4.2 §2.2 补「同数量但名称/顺序不同」回归

| 检查项 | 结果 | 证据 |
|---|---|---|
| 使用临时目录与假权重 | ✅ | 全部在 `tmp_path` 内写空 `best_model.pth` 与 `class_names.json`，配合既有 `fake_predictor` fixture（monkeypatch 内部 `Predictor`） |
| 不触碰真实权重/正式数据 | ✅ | 未加载 `artifacts/**`，未访问 `data/**` |
| 断言明确失败 | ✅ | 三个用例都用 `pytest.raises(ValueError)` |
| 保留索引级错误信息 | ✅ | 断言 `class mapping mismatch at index 0` / `at index 2`，以及 `checkpoint='...'` 与 `dataset='...'` 两侧标签 |
| 不落入「数量」分支 | ✅ | 断言 `"class count mismatch" not in message` |
| 不静默回退/重排 | ✅ | 第三个用例断言异常抛出后 `service is None` |
| 未修改生产代码 | ✅ | `backend/app/services/predictor.py` 与 `ml/model.py` 本轮**零改动** |
| 测试名清晰表达语义 | ✅ | 形如 `test_same_class_count_but_reordered_names_refuses_to_start` |

**覆盖的两个维度**：

1. **顺序不同**：`["chihuahua","boxer","beagle"]` —— 与 `FAKE_CLASSES` 同集合，仅顺序反转 → index 0 处 `checkpoint='beagle'` vs `dataset='chihuahua'`
2. **名称不同**：`["beagle","boxer","pug"]` —— 前两项一致，仅 index 2 不同 → 断言 `at index 2`，且断言**不含** `at index 0` / `at index 1`（证明定位精确）

---

## 5. 缓存说明

测试过程生成的缓存（`__pycache__`、`.pytest_cache`、`frontend/node_modules/.vite`、
`frontend/dist`）**按任务要求未清理**，它们已被 `.gitignore` 覆盖
（`git status --short` 中不出现），本轮及后续提交均排除在外。

---

## 6. 门禁后的下一步

三项全绿，按任务 §4 顺序执行 A(10) → B(9) → C(2) → D(4) 四组提交。
每组提交前置条件与核对项见 `commits.md`。
