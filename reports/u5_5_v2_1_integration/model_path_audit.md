# 模型路径与类别映射审计（U5.5）

> 审计时间：2026-10-19
> 目的：确认**日常启动入口**实际加载的模型与类别表，以及所有与模型路径、
> 类别映射、候选开关有关的环境变量读取逻辑。

---

## 1. 审计结论（先看这里）

| 问题 | 结论 |
|---|---|
| 接入前为什么不加载 V2.1？ | 两个独立原因叠加：①`Settings` **没有 `class_names_path`**，`main.py` 也不透传 → `PredictorService` 恒用根目录 **37 类**表校验；②`启动后端.bat` / `启动系统.bat` **硬编码检查 V1.1 文件且不设任何 `CATDOG_*`**，必然以默认 V1.1 启动 |
| 接入后默认加载什么？ | **V2.1（136 类）**：`artifacts/v2_1_136classes_seed42/best_model.pth` + 同目录 `class_names.json`；日志实测 `version=v2_1_136classes_candidate classes=136` |
| 权重与类名表会不会错配？ | **不会静默错配**：数量不同时 `PredictorService` 抛 `ValueError`（含两个真实路径与两侧计数），`/api/health` 的 `model_error` 给出"checkpoint 有 X 类但 class_names.json 有 Y 类"，进程不会退回随机模型 |
| V1.1 文件是否被动过？ | **完全没有**。根目录 `best_model.pth` / `class_names.json` / `model_version.json` SHA256 与任务开始前一致 |
| 能否回退？ | 可以，只改环境变量、不动文件。见 `rollback.md`（已实测：37 类、`v1_1_37_optimized`、候选安全为空） |

---

## 2. 启动入口检查

| 文件 | 接入前 | 接入后 | 是否修改 |
|---|---|---|---|
| `启动系统.bat` | 检查 `.venv`、`frontend\package.json`、**`artifacts\best_model.pth`**；`start` 两个子脚本 | 检查 `.venv`、`frontend\package.json`、**`artifacts\v2_1_136classes_seed42\best_model.pth` 与 `class_names.json`**；已设 `CATDOG_*` 时跳过默认路径检查；缺失时打印回退命令 | **是** |
| `启动后端.bat` | 检查 `.venv`、**`artifacts\best_model.pth`**、**`artifacts\class_names.json`**；设 `TORCH_HOME`；`python -m uvicorn backend.app.main:app --port 8000`；**不设 `CATDOG_*`** | 同上，检查改为 **V2.1 目录两文件**；**仍不设任何 `CATDOG_*`**（保证用户显式覆盖生效）；缺失时打印回退命令 | **是** |
| `启动前端.bat` | 只启动 Vite | 不变 | **否** |

> **真实入口实测证据**（`real_launcher_backend_stderr.log`）：
> ```
> INFO:     class mapping verified against class_names.json (136 classes)
> INFO:     model ready: version=v2_1_136classes_candidate arch=resnet18 classes=136 device=cuda (weights: best_model.pth)
> ```
> 对应 `/api/health`：
> ```json
> {"status":"ok","model_loaded":true,"num_classes":136,"model_weights":"best_model.pth","model_error":null,"version":"1.0.0"}
> ```

---

## 3. 代码级路径读取逻辑

### 3.1 `backend/app/config.py`

| 配置项 | 环境变量 | 默认值（接入后） |
|---|---|---|
| `weights_path` | `CATDOG_WEIGHTS_PATH` | `artifacts/v2_1_136classes_seed42/best_model.pth` |
| `class_names_path` | `CATDOG_CLASS_NAMES_PATH` | `artifacts/v2_1_136classes_seed42/class_names.json` |
| `candidate_group_enabled` | `CATDOG_CANDIDATE_GROUP_ENABLED` | **`True`**（接入前为 `False`） |
| `device` | `CATDOG_DEVICE` | `auto` |
| `db_path` | `CATDOG_DB_PATH` | `data/app.db` |
| `upload_dir` | `CATDOG_UPLOAD_DIR` | `uploads/` |

布尔解析 `_env_bool`：`1/true/yes/on` → True，`0/false/no/off` → False，
**其他值回退到默认值**（当前默认 True）。

### 3.2 `backend/app/main.py`

```python
app.state.predictor = PredictorService(
    weights_path=settings.weights_path,
    device=settings.device,
    class_names_path=settings.class_names_path,     # U5.5 新增透传
    candidate_group_enabled=settings.candidate_group_enabled,
)
```

`/api/health` 新增 `model_weights`（仅文件名），用于证明"实际加载了哪个权重"。

### 3.3 `backend/app/services/predictor.py`

```python
if class_names_path and Path(class_names_path).exists():
    saved = json.loads(...)
    try:
        verify_class_mapping(self.class_names, saved)
    except ValueError as exc:
        if len(self.class_names) != len(saved):
            raise ValueError(
                f"class count mismatch between checkpoint and class names file: "
                f"weights=... ({len(self.class_names)} classes), "
                f"class_names=... ({len(saved)} classes). ...") from exc
        raise
```

- **数量不同** → 明确失败（含两侧计数与两个路径）
- **数量相同但顺序/名称不同** → 保留 `verify_class_mapping` 的索引级消息
- **`class_names_path=None`** → 跳过校验（测试专用路径）

### 3.4 `ml/model.py` 常量（未修改）

| 常量 | 值 | 说明 |
|---|---|---|
| `BEST_WEIGHTS_PATH` | `artifacts/best_model.pth` | V1.1，仍是"回退目标"，未被改写 |
| `CLASS_NAMES_PATH` | `artifacts/class_names.json` | 37 类，仅作 `PredictorService` 的构造函数默认值（生产路径已显式传入 `settings.class_names_path`） |

> 注意：`PredictorService` 的形参默认值仍是 `CLASS_NAMES_PATH`（37 类），
> 但**生产路径一定显式传参**；只有单元测试会走默认值。

---

## 4. 权重与类别映射的配对校验

| 检查 | 结果 |
|---|---|
| V2.1 `class_names.json` 类别数 | 136，唯一 136 |
| V2.1 checkpoint `num_classes` | 136 |
| checkpoint 内 `class_names` 与 `class_names.json` **顺序** | **完全一致**（脚本比对 `True`） |
| `fc.weight` 形状 | `(136, 512)` |
| 根目录 `artifacts/class_names.json` | **37 类，未改动** |
| 37/136 人为错配 | **抛出 `ValueError`**，消息含 `class count mismatch`、`136 classes`、`37 classes`、`class_names.json`、`best_model.pth`（单测 `tests/test_predictor_service.py` 固化） |

---

## 5. 候选开关

| 项目 | 值 |
|---|---|
| 默认值 | **`True`**（随 V2.1 一起启用，U5.2/U5.3/U5.4 已验收） |
| 候选成员 | APBT、AmStaff、SBT、American Bulldog（**未改动**） |
| 阈值 | `mass >= 0.30`、`margin <= 0.40`（**未重新扫描、未调整**） |
| `threshold_version` | `val-2026-10-19-four-breed-b1`（**未变**） |
| 显式关闭 | `CATDOG_CANDIDATE_GROUP_ENABLED=false`（实测：候选区消失、原始 Top-K 不变） |
| V1.1 回退时的安全性 | 37 类缺 APBT/AmStaff → `build_candidate_group` 返回 `None` → `candidate_group: null`，**不崩溃**（已实测） |

---

## 6. 环境变量「是否被启动脚本覆盖」

| 脚本 | 是否设置 `CATDOG_*` | 结果 |
|---|---|---|
| `启动系统.bat` | **否** | 用户预先设置的 `CATDOG_*` 会传给子进程 `启动后端.bat` |
| `启动后端.bat` | **否** | 用户显式设置优先；未设置时走 `config.py` 默认（V2.1） |
| `启动前端.bat` | **否** | 与模型无关 |

> 因此 `rollback.md` 中"先 `set` 再运行 `启动系统.bat`"的方式是有效的。

---

## 7. 审计用的只读命令（可复现）

```powershell
cd E:\CatDogBreedNet

# 1. 默认配置最终态
.venv\Scripts\python.exe -c "import sys;sys.path.insert(0,'.');from backend.app.config import Settings;s=Settings.from_env();print(s.weights_path);print(s.class_names_path);print(s.candidate_group_enabled)"

# 2. 权重与类名表配对
.venv\Scripts\python.exe -c "import json,torch;n=json.load(open('artifacts/v2_1_136classes_seed42/class_names.json',encoding='utf-8'));p=torch.load('artifacts/v2_1_136classes_seed42/best_model.pth',map_location='cpu',weights_only=True);print(len(n),p['num_classes'],list(p['class_names'])==list(n))"

# 3. 真实入口健康状态
cmd /c 启动后端.bat      # 另开窗口；等待启动完成后：
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

---

## 8. 审计中确认的既有事实（非本轮引入）

1. `PredictorService` 的 `class_names_path` 默认值指向 37 类表——这是 U5.5 之前
   "无法加载 V2.1"的根因之一。
2. `启动后端.bat` 从项目建立之初就检查 `artifacts\best_model.pth`，属于历史设计，
   在 V1.1 为默认模型时是正确的；本轮随默认模型切换同步更新。
3. `ml/model.py` 的 `BEST_WEIGHTS_PATH` / `CLASS_NAMES_PATH` 常量**刻意保持不变**：
   它们仍是 V1.1 的路径引用，用于回退与历史脚本兼容。
