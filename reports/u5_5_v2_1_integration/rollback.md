# V2.1 → V1.1 回退手册（已实测）

> 本手册中的环境变量名与命令**全部与最终代码一致**（`backend/app/config.py`），
> 并已在 2026-10-19 实测通过（见第 5 节证据）。
> **回退只改环境变量，不覆盖、不复制、不重命名任何权重文件，也不改动数据库或历史记录。**

---

## 1. 回退前须知

| 项目 | 现状（默认） |
|---|---|
| 默认权重 | `artifacts\v2_1_136classes_seed42\best_model.pth`（136 类） |
| 默认类名表 | `artifacts\v2_1_136classes_seed42\class_names.json`（136 类） |
| 默认候选开关 | `True`（四类 B1：APBT / AmStaff / SBT / American Bulldog） |
| V1.1 文件位置 | `artifacts\best_model.pth`（37 类）、`artifacts\class_names.json`（37 类）——**从未被改写** |

**关键约束**：权重与类名表必须**成对**切换。136 类权重配 37 类表会直接启动失败
（`class count mismatch`），这是刻意的安全网。

---

## 2. 方法 A：临时回退（仅当前命令行窗口生效，推荐用于排障）

在**运行启动脚本的同一个命令行窗口**里先设置两个环境变量，再启动：

```bat
cd /d E:\CatDogBreedNet

set CATDOG_WEIGHTS_PATH=E:\CatDogBreedNet\artifacts\best_model.pth
set CATDOG_CLASS_NAMES_PATH=E:\CatDogBreedNet\artifacts\class_names.json

rem 可选：同时关闭候选提示
set CATDOG_CANDIDATE_GROUP_ENABLED=false

rem 然后启动（二者等价，任选其一）
启动后端.bat
rem 或：
启动系统.bat
```

> `启动系统.bat` 与 `启动后端.bat` **不设置也不清除任何 `CATDOG_*`**，
> 因此上面 `set` 的值会被子进程继承并生效。
> 关闭该命令行窗口后，回退自动失效。

---

## 3. 方法 B：永久回退（改代码默认值）

编辑 `backend/app/config.py` 两行（**只改默认值，不动任何权重文件**）：

```python
# 回退到 V1.1（37 类）
weights_path: Path = ARTIFACTS_DIR / "best_model.pth"
class_names_path: Path = ARTIFACTS_DIR / "class_names.json"
candidate_group_enabled: bool = False      # 可选：37 类下候选组本就是安全空值
```

同时把 `Settings.from_env()` 里的两个默认字符串改回
`str(ARTIFACTS_DIR / "best_model.pth")` / `str(ARTIFACTS_DIR / "class_names.json")`，
并（可选）把 `_env_bool("CANDIDATE_GROUP_ENABLED", True)` 改回 `False`。

---

## 4. 确认回退成功

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

**期望结果**：

```json
{
  "status": "ok",
  "model_loaded": true,
  "num_classes": 37,
  "model_weights": "best_model.pth",
  "model_error": null,
  "version": "1.0.0"
}
```

判定要点（按重要性排序）：

1. **`num_classes` 必须为 `37`** —— 这是"实际加载了 V1.1"的硬证据；
2. `model_weights` 为 `best_model.pth`（V1.1 与 V2.1 同名，**不能只看这一项**）；
3. 后端启动日志应出现：
   `class mapping verified against class_names.json (37 classes)`
   与 `model ready: version=v1_1_37_optimized ... classes=37`；
4. 预测一次，`candidate_group` 应为 `null`（37 类缺 APBT/AmStaff，候选组安全返回空）。

> **只看 `model_weights` 不足以判断版本**，因为 V1.1 与 V2.1 的权重文件都叫
> `best_model.pth`；**必须同时看 `num_classes`**。

---

## 5. 实测证据（2026-10-19）

以方法 A 启动后：

```
GET /api/health
{"status":"ok","model_loaded":true,"num_classes":37,
 "model_weights":"best_model.pth","model_error":null,"version":"1.0.0"}

后端日志
INFO:     class mapping verified against class_names.json (37 classes)
INFO:     model ready: version=v1_1_37_optimized arch=resnet18 classes=37 device=cuda (weights: best_model.pth)

预测一次（american_bulldog_121.jpg）
HTTP 200
num_classes = 37
top1 = {'breed': 'american_bulldog', 'confidence': 0.644206}
candidate_group = None        ← 候选组安全为空，未崩溃
```

---

## 6. 回退时**不要**做的事

| 禁止 | 原因 |
|---|---|
| 覆盖 `artifacts\class_names.json` 为 136 类内容 | 会让 V1.1 无法启动，且破坏历史兼容 |
| 把 V2.1 的 `class_names.json` 复制到根目录 | 同上 |
| 重命名/移动任何 `.pth` 文件 | 会破坏 `model_version.json` 关联与 V1 备份 |
| 删除 `artifacts\v2_1_136classes_seed42\` | 想再切回 V2.1 就得重新训练 |
| 改动 `data\app.db` 或 `uploads\` | 历史记录与上传文件与模型版本无关 |
| `git reset --hard` / `git clean` | 会丢失本次接入与既有的未提交改动 |

---

## 7. 最小健康验证清单（回退后逐项打勾）

- [ ] `/api/health` 返回 `num_classes == 37`
- [ ] 启动日志出现 `classes=37` 与 `version=v1_1_37_optimized`
- [ ] 上传一张图 → 200，`predictions` 有 3 条，`candidate_group` 为 `null`
- [ ] 前端识别页正常显示中文犬种名（V1.1 的 37 类映射仍完整保留在 136 条映射中）
- [ ] 历史页可打开，原有记录仍显示原中文名
- [ ] `uploads\` 与 `data\app.db` 未被改动（行数与回退前一致）

---

## 8. 回退后的重新启动

```bat
rem 关闭旧的命令行窗口（或 Ctrl+C 停止 uvicorn）
rem 然后用回退设置重新启动
启动系统.bat
```

前端无需任何改动：候选区是否显示完全由后端响应决定（`candidate_group.triggered`）。
