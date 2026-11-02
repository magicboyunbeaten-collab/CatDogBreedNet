# U6.3：回归测试结果

> 生成时间：2026-10-21
> 工作目录：`E:\CatDogBreedNet`（除前端命令外）
> 说明：以下命令均为**实际执行**；返回码与通过数如实记录，未删除或放宽任何断言。

---

## 1. 后端全量测试

**命令**（工作目录 `E:\CatDogBreedNet`）：

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q
```

**结果**：

```
265 passed, 4 warnings in 14.35s
```

| 项目 | 值 |
|---|---|
| 返回码 | **0** |
| 通过 | **265** |
| 失败 / 错误 | 0 |
| 警告 | 4（`PIL.Image.getdata` 弃用提示，既有） |
| 基线（U6.2 结束时） | 265 passed |
| 与基线差异 | **无**（本轮未改任何源码或测试） |

---

## 2. 前端全量测试

**命令**（工作目录 `E:\CatDogBreedNet\frontend`）：

```powershell
npm test          # 实际执行：npx vitest run（package.json 中 test = "vitest run"）
```

**结果**：

```
 Test Files  12 passed (12)
      Tests  85 passed (85)
   Duration  3.78s
```

| 项目 | 值 |
|---|---|
| 返回码 | **0** |
| 测试文件 | **12 passed** |
| 用例 | **85 passed** |
| 失败 | 0 |
| 基线（U6.2 结束时） | 85 passed / 12 files |
| 与基线差异 | **无** |

> 执行方式：`cmd /c "npm test > .cache\u63_feall.log 2>&1"` 后台运行后读取日志
> （PowerShell 直接调用 `npm test` 在此环境下不可靠）。

---

## 3. 前端生产构建

**命令**（工作目录 `E:\CatDogBreedNet\frontend`）：

```powershell
npm run build
```

**结果**：

```
✓ built in 1.69s
```

| 项目 | 值 |
|---|---|
| 返回码 | **0** |
| 状态 | **成功** |
| 警告 | chunk > 500 kB（既有，来自 Element Plus 等依赖，非本轮引入） |

---

## 4. 汇总

| 命令 | 返回码 | 结果 |
|---|---|---|
| `.venv\Scripts\python.exe -m pytest tests/ -q` | 0 | **265 passed** |
| `npm test`（frontend） | 0 | **85 passed / 12 files** |
| `npm run build`（frontend） | 0 | **成功 1.69s** |

**结论：三项全部通过，与基线完全一致，无回归。**

---

## 5. 未执行的操作

- 未运行任何训练脚本（`ml/train.py` / `scripts/u6_run_experiment.py` 等）；
- 未访问 `data/v2_processed/test`；
- 未使用正式 `data/app.db` 或项目 `uploads/` 做图片预测
  （所有上传均走 `reports/u6_3_default_runtime_and_freeze/runtime_*` 隔离存储）。
