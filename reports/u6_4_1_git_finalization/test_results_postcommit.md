# U6.4.1：提交后完整回归结果

> 执行时间：2026-10-21（四组提交 A→B→C→D 全部完成之后）
> HEAD：`ca86b0b`
> 要求：三项全部退出码 0。

---

## 0. 结论

| # | 命令 | 工作目录 | 退出码 | 结果 |
|---:|---|---|---:|---|
| 1 | `.venv\Scripts\python.exe -m pytest tests/ -q` | `E:\CatDogBreedNet` | **0** | **268 passed**, 4 warnings |
| 2 | `npm test` | `E:\CatDogBreedNet\frontend` | **0** | **85 passed / 12 files** |
| 3 | `npm run build` | `E:\CatDogBreedNet\frontend` | **0** | **成功 816ms** |

**提交后回归全部通过**，与提交前基线一致。

---

## 1. 后端全量测试

```powershell
cd E:\CatDogBreedNet
.venv\Scripts\python.exe -m pytest tests/ -q
```

```
268 passed, 4 warnings in 13.74s
PYTEST_EXIT=0
```

| 项目 | 提交前 | 提交后 | 差异 |
|---|---:|---:|---|
| 通过 | 268 | **268** | 0 |
| 失败/错误 | 0 | **0** | 0 |
| 警告 | 4 | 4 | 0（均为既有 Pillow 弃用提示） |

---

## 2. 前端测试

```powershell
cd E:\CatDogBreedNet\frontend
npm test
```

```
 ✓ tests/router.test.js (4 tests) 3ms
 Test Files  12 passed (12)
      Tests  85 passed (85)
   Duration  3.14s
```

| 项目 | 提交前 | 提交后 | 差异 |
|---|---:|---:|---|
| 测试文件 | 12 passed | **12 passed** | 0 |
| 用例 | 85 passed | **85 passed** | 0 |
| 失败 | 0 | **0** | 0 |

---

## 3. 前端生产构建

```powershell
cd E:\CatDogBreedNet\frontend
npm run build
```

```
✓ built in 816ms
BUILD_EXIT=0
```

| 项目 | 提交前 | 提交后 | 差异 |
|---|---|---|---|
| 结果 | 成功 1.70s | **成功 816ms** | 无（构建时间波动） |
| 退出码 | 0 | **0** | 0 |

---

## 4. 各组提交后的中间测试（记录在案）

| 时点 | 命令 | 结果 |
|---|---|---|
| A 后 | `pytest tests/test_candidate_group.py tests/test_api.py -q` | **87 passed**（退出码 0） |
| B 后 | `pytest tests/ -q` | **268 passed**（退出码 0） |
| B 后 | `npm test` | **85 passed / 12 files**（退出码 0） |
| C 后 | `.bat` 静态检查 + `npm run build` | 编码/行数/只读语义通过；build 退出码 0 |
| D 后 | `pytest tests/test_train_extensions.py -q` | **39 passed**（退出码 0） |

---

## 5. Git 状态核验（任务 §5 要求）

| 检查项 | 结果 |
|---|---|
| `git rev-parse HEAD` | `ca86b0b...`（见 `git_log_after.txt`） |
| `git log -4 --oneline` | **恰好包含本任务 4 个有序提交** A→B→C→D ✅ |
| `git diff --cached --stat` | **空** ✅ |
| `git status --short` 中 `M`（已跟踪修改） | **0** ✅ —— A/B/C/D 四组不再遗留任何未提交的已跟踪改动 |

`git log -6 --oneline` 实测：

```
ca86b0b Extend training infrastructure for warm-start and pair experiments   ← D
62c86bf Use V2.1 defaults in Windows launchers                               ← C
bfb9fd0 Add regression tests for prediction and candidate UX                 ← B
52165ca Integrate V2.1 136-class prediction and candidate groups             ← A
547c55d v2训练前                                                             ← 起始 HEAD
301174a U3：V2 扩展数据源审核与准备（135 类，未训练）
```

---

## 6. 保护核验（任务 §5 要求）

`protection_snapshot_before.json` / `_after.json` 自动比对：**全部受保护对象一致**。

| 检查项 | 结果 |
|---|---|
| V1.1 `artifacts/best_model.pth` SHA256 | `89ef468f199c6d1550fec2638c5ea6f8ef7ad543e57f8ec82c4263c121b1a256` —— **与开工前一致** |
| V2.1 四文件（`best_model.pth` / `class_names.json` / `model_version.json` / `experiment_config.json`） | **一致**（只读加载，未写入） |
| 五个数据目录 | 文件数与字节 **一致** |
| 正式 `data/app.db` | **142 条**，`integrity_check: ok` —— **一致，写入 0 次** |
| 项目 `uploads/` | **142 文件** —— **一致，写入 0 次** |
| 默认 `weights_path` | `artifacts\v2_1_136classes_seed42\best_model.pth` —— **未变** |
| 默认 `class_names_path` | `artifacts\v2_1_136classes_seed42\class_names.json` —— **未变** |
| `candidate_group_enabled` | **True** —— **未变** |
| 训练 | **未运行任何训练脚本** |
| `data/v2_processed/test` | **访问 0 次** |
| `reports/u6_4_git_freeze_review/` 等既有报告 | **未写入、未覆盖** |

---

## 7. 缓存说明

测试与构建过程生成的缓存（`__pycache__`、`.pytest_cache`、`frontend/node_modules/.vite`、
`frontend/dist`）**按任务要求未清理**。它们已被 `.gitignore` 覆盖，
在 `git status --short` 中**不出现**，也未进入任何提交。

---

## 8. 复现命令

```powershell
cd E:\CatDogBreedNet
.venv\Scripts\python.exe -m pytest tests/ -q

cd E:\CatDogBreedNet\frontend
npm test
npm run build
```
