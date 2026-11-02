# U6.1-A：warm-start 初始化继承审计

> **结论：通过。** 上一轮 5 个 U6 实验的 136→136 warm-start **确实从 V2.1 继承了分类头**
> （含张量级逐位一致的硬证据），因此**旧实验结论可用，无需重跑**。
>
> 生成时间：2026-10-20
> 执行脚本：`scripts/u6_warm_start_audit.py`（只读，不写盘、不训练、不访问 test split）
> 数据：`warm_start_audit_data.json`

---

## 1. 背景与判定规则

U6 报告曾指出：旧实现无条件跳过分类头，导致 136→136 warm-start 会把 `fc.weight` /
`fc.bias` 重置为随机值。若如此，则上一轮 exp01/exp02/exp04 都**不是从 V2.1 初始化**，
其负结果不能归因于实验变量。

任务 §2 的判定规则：

- 若日志可证明继承 → 如实记录，**不重跑旧实验**；
- 若无法证明 → 旧实验标为「初始化证据不足」，不得用于声称变量无效；
- 若当前初始化代码或单测失败 → 先做最小修复并补测试。

---

## 2. 源码级核验（`ml/train.py::initialize_from_checkpoint`）

| 检查项 | 结果 |
|---|---|
| `same_classes` 分支存在 | **PASS** |
| 类别名完全一致时 `head_keys` 为空（即不移除 `fc.*`） | **PASS** |
| `transfer` 按 `head_keys` 过滤（`head_keys` 为空时包含 `fc.*`） | **PASS** |
| 调用点透传 `target_class_names=class_names` | **PASS** |
| `head_transferred` 记入 `experiment_config.json` | **PASS** |

关键实现：当 `target_class_names` 与 checkpoint 的 `class_names` **逐一相等**时，
`head_keys = set()`，于是 `transfer` 包含全部 122 个张量（含 `fc.weight`/`fc.bias`）；
`permitted_missing` 同时设为空集，因此若有任何参数未加载都会**直接抛错**而非静默降级。

---

## 3. 内存级单元验证（不写盘、不训练）

为排除"配置写了但实际没加载"的可能，本轮做了**张量级**比对：

| 验证 | 结果 |
|---|---|
| 继承路径：`head_transferred=True`、`loaded_keys=122`、`skipped_keys=[]` | **PASS** |
| **`fc.weight` / `fc.bias` 与 V2.1 源张量 `torch.equal` 逐位一致** | **PASS** |
| 反例（类别名少一项）：`head_transferred=False`、`skipped_keys=['fc.bias','fc.weight']` | **PASS**（按原逻辑重建并断言） |

> 这是"加载键统计"之外的**更强证据**：直接证明 `fc.*` 的数值就是 V2.1 的数值，
> 不是重新初始化后的随机值。

---

## 4. 既有 5 个 U6 实验的初始化证据

| 实验 | seed | image_size | pair jitter | pair sampler | init_sha256=V2.1 | head_transferred | loaded | skipped | 类别顺序 SHA 一致 |
|---|---|---:|---|---|---|---|---|---|---|
| `exp01_pair_color_jitter` | 42 | 224 | 0.2,0.2,0.3,0.05 | 1.0 | **是** | **True** | 122 | (无) | **是** |
| `exp02_pair_sampler` | 42 | 224 | — | 3.0 | **是** | **True** | 122 | (无) | **是** |
| `exp04_resolution` | 42 | 256 | — | 1.0 | **是** | **True** | 122 | (无) | **是** |
| `exp04_resolution` | 7 | 256 | — | 1.0 | **是** | **True** | 122 | (无) | **是** |
| `exp04_resolution` | 2024 | 256 | — | 1.0 | **是** | **True** | 122 | (无) | **是** |

- `init_from.sha256` 全部 = `423e218a29230f8248e071e7fb47b88afb2c1f2b67fb860224f6f319041821e1`
  （= V2.1 `best_model.pth` 的 SHA256）
- `class_names` 与 V2.1 `class_names.json` **完全一致**，`class_order_sha256` 一致
- `loaded_keys=122` = V2.1 state_dict 张量总数，`skipped_keys=[]`

**判定：5 个旧实验的初始化证据充分，可用于既有结论；无需重跑。**

---

## 5. `--lr` 语义说明（避免"默默忽略参数"）

任务要求"若 CLI 没有直接支持某个参数，先做最小兼容实现并添加单测，不能默默忽略参数"。
本轮低学习率协议用到的 `--lr-head` / `--lr-backbone` **已被 CLI 直接支持**，
但需说明 `--lr 1e-3` 的作用，以免误读：

`ml/train.py::build_optimizer` 的实现为：

```python
if lr_head is None and lr_backbone is None:
    return AdamW([...], lr=lr, weight_decay=weight_decay)
...
groups.append({"params": head_params, "name": "head",
               "lr": lr if lr_head is None else lr_head})
groups.append({"params": backbone_params, "name": "backbone",
               "lr": lr if lr_backbone is None else lr_backbone})
```

**结论**：当 `--lr-head` 与 `--lr-backbone` 均显式给出时，head 组与 backbone 组的
实际学习率**完全由这两个参数决定**，`--lr` 仅作为分组缺省值与 AdamW 构造参数，
对参数更新**无效**。

因此本轮设置 `--lr-head 1e-4 --lr-backbone 5e-5` 后，**有效学习率即为 1e-4 / 5e-5**；
`--lr 1e-3` 保留只是为了与既有 `BASELINE_ARGS` 的元数据一致，不代表实际更新幅度。
这一点已在 `experiment_config.json`（`lr` / `lr_head` / `lr_backbone` 三字段并存）与
本审计中同时写明。

---

## 6. 后端测试

```
.venv\Scripts\python.exe -m pytest tests/ -q
→ 250 passed, 4 warnings in 14.98s
```

包含 `tests/test_train_extensions.py` 中与 `initialize_from_checkpoint` 相关的
断言（类别数不同必须重建头、张量数量必须精确匹配、异常必须抛错）。

---

## 7. 审计结论

1. **当前初始化代码正确**：136→136 同类别名时连分类头一起继承，且未加载任何必需
   参数会直接抛错。
2. **上一轮 5 个实验的分类头确实继承自 V2.1**，`init_sha256` 与 V2.1 一致、
   `fc.*` 张量逐位一致。
3. **旧实验结论可用**：exp01/exp02 的负结果与 exp04 的正向结果都建立在正确的
   warm-start 之上，不需要重跑。
4. **可以开始 U6.1-B 训练**：本轮三个实验将从同一份 V2.1 checkpoint 初始化，
   并会在日志与 `experiment_config.json` 中再次记录 `head_transferred=True`
   与 `init_from.sha256`。
