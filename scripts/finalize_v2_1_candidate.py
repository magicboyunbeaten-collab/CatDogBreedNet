#!/usr/bin/env python
"""收尾 V2.1 候选模型目录：model_version.json / training_history.csv / 报告。

用法（在仓库根目录执行）::

    python scripts/finalize_v2_1_candidate.py \
        --model-dir artifacts/v2_1_136classes_seed42 \
        --command "python -m ml.train --data-dir data/v2_processed ..."

前置：训练（``python -m ml.train``）、test 评估（``python -m ml.evaluate
--split test``）与子集分析（``scripts/evaluate_v2_1_subsets.py``）均已完成。

本脚本只读候选目录与 ``reports/v2_class_catalog.json``，只写候选目录内的
``model_version.json``、``training_history.csv`` 与
``V2_1_训练与评估报告.md``；**不会**写 ``artifacts/model_version.json``。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

VERSION_ID = "v2_1_136classes_candidate"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fmt(value, digits: int = 4) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}"
    return "—"


def load_matrix(path: Path) -> tuple[list[list[int]], list[str]]:
    """读取 ``true\\pred`` 混淆矩阵 CSV。"""
    import csv as _csv

    with path.open(encoding="utf-8") as handle:
        reader = _csv.reader(handle)
        header = next(reader)
        labels = header[1:]
        rows = [[int(value) for value in row[1:]] for row in reader if row]
    return rows, labels


def top_confusions(rows: list[list[int]], labels: list[str],
                   label: str, limit: int = 3) -> list[tuple[str, int]]:
    """返回真实类别为 ``label`` 时最常被误判成的其他类别。"""
    if label not in labels:
        return []
    index = labels.index(label)
    row = rows[index]
    pairs = [(labels[j], row[j]) for j in range(len(labels))
             if j != index and row[j] > 0]
    return sorted(pairs, key=lambda kv: -kv[1])[:limit]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model-dir", type=Path,
                        default=_REPO_ROOT / "artifacts"
                        / "v2_1_136classes_seed42")
    parser.add_argument("--command", default="", help="training command line")
    parser.add_argument("--train-log-name", default="train.log")
    args = parser.parse_args(argv)

    model_dir: Path = args.model_dir
    required = ["best_model.pth", "last_model.pth", "class_names.json",
                "experiment_config.json", "train_log.csv", "metrics.json",
                "test_metrics.json", "confusion_matrix.csv",
                "classification_report.csv"]
    missing = [name for name in required if not (model_dir / name).exists()]
    if missing:
        print(f"[finalize] missing artifacts: {missing}", file=sys.stderr)
        return 1

    config = json.loads((model_dir / "experiment_config.json").read_text(
        encoding="utf-8"))
    metrics = json.loads((model_dir / "metrics.json").read_text(
        encoding="utf-8"))
    test_metrics = json.loads((model_dir / "test_metrics.json").read_text(
        encoding="utf-8"))
    class_names = json.loads((model_dir / "class_names.json").read_text(
        encoding="utf-8"))

    if len(class_names) != 136:
        print(f"[finalize] class_names has {len(class_names)} entries, "
              f"expected 136", file=sys.stderr)
        return 1
    if metrics["num_classes"] != 136:
        print("[finalize] metrics.num_classes != 136", file=sys.stderr)
        return 1

    # ---- training_history.csv（保留原 train_log.csv）-------------------
    source_log = model_dir / "train_log.csv"
    history = model_dir / "training_history.csv"
    shutil.copy2(source_log, history)

    # ---- model_version.json --------------------------------------------
    best_sha = sha256_file(model_dir / "best_model.pth")
    names_sha = sha256_file(model_dir / "class_names.json")
    version = {
        "version_id": VERSION_ID,
        "num_classes": 136,
        "status": "candidate",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "checkpoint": {
            "best": "best_model.pth",
            "last": "last_model.pth",
            "best_sha256": best_sha,
            "best_bytes": (model_dir / "best_model.pth").stat().st_size,
        },
        "class_names": "class_names.json",
        "class_names_sha256": names_sha,
        "arch": config.get("arch"),
        "trained_on": config.get("data_dir"),
        "monitor": config.get("monitor"),
        "best_epoch": config.get("best_epoch"),
        "best_val_acc": config.get("best_val_acc"),
        "best_val_macro_f1": config.get("best_val_macro_f1"),
        "init_from": config.get("init_from"),
        "test_metrics": {
            "accuracy": test_metrics.get("accuracy"),
            "macro_f1": test_metrics.get("macro_f1"),
            "weighted_f1": test_metrics.get("weighted_f1"),
        },
        "note": ("候选模型，**未**接入正式系统；后端默认仍加载 "
                 "artifacts/best_model.pth（V1.1，37 类）。"),
    }
    (model_dir / "model_version.json").write_text(
        json.dumps(version, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- 人类可读报告 ---------------------------------------------------
    groups = metrics["groups"]
    lines: list[str] = []
    add = lines.append
    add("# V2.1（136 类）候选模型训练与评估报告")
    add("")
    add(f"- 版本标识：`{VERSION_ID}`（**候选**，未接入正式系统）")
    add(f"- 生成时间：{version['created_at']}")
    add(f"- 输出目录：`{model_dir.as_posix()}`")
    add("")

    add("## 1. 训练命令")
    add("")
    add("```powershell")
    add(args.command or "（未记录）")
    add("```")
    add("")

    add("## 2. 初始化来源与校验")
    add("")
    init = config.get("init_from") or {}
    if init:
        add("| 项目 | 值 |")
        add("|---|---|")
        add(f"| 来源 checkpoint | `{init.get('path')}` |")
        add(f"| 来源 SHA256 | `{init.get('sha256')}` |")
        add(f"| 来源架构 / 类别数 | {init.get('source_arch')} / "
            f"{init.get('source_num_classes')} |")
        add(f"| 已迁移张量数 | {init.get('loaded_keys')} |")
        add(f"| 重新初始化 | {init.get('skipped_keys')} |")
        add(f"| 跳过原因 | {init.get('skipped_reason')} |")
        add("")
        add("> 加载结果经断言校验：缺失键必须恰为分类层、不得有未预期键，"
            "不存在宽泛 `strict=False` 静默吞参。")
    else:
        add("未使用 `--init-from`（从 ImageNet 预训练权重开始）。")
    add("")

    add("## 3. 训练配置")
    add("")
    add("| 参数 | 值 |")
    add("|---|---|")
    for key, label in (
            ("arch", "架构"), ("num_classes", "类别数"),
            ("data_dir", "训练数据"), ("seed", "随机种子"),
            ("batch_size", "batch size"), ("lr_head", "分类头学习率"),
            ("lr_backbone", "骨干学习率"), ("weight_decay", "权重衰减"),
            ("optimizer", "优化器"), ("scheduler", "调度器"),
            ("loss", "损失函数"), ("augment_preset", "数据增强"),
            ("freeze_strategy", "冻结策略"),
            ("early_stopping_patience", "early stopping patience"),
            ("monitor", "选模指标"), ("image_size", "输入尺寸")):
        add(f"| {label} | {config.get(key)} |")
    add("")

    add("## 4. 训练结果")
    add("")
    add(f"- epochs 请求 / 实际：{config.get('epochs_requested')} / "
        f"{config.get('epochs_completed')}")
    add(f"- 最佳 epoch：**{config.get('best_epoch')}**"
        f"（按 `{config.get('monitor')}` 选模）")
    add(f"- 最佳验证指标：val_macro_f1 **{fmt(config.get('best_val_macro_f1'))}**，"
        f"val_acc **{fmt(config.get('best_val_acc'))}**")
    add(f"- 总训练耗时：{config.get('total_seconds')} 秒"
        f"（约 {float(config.get('total_seconds') or 0) / 60:.1f} 分钟）")
    add(f"- 环境：Python {config['environment']['python']} / "
        f"torch {config['environment']['torch']} / "
        f"{config['environment']['gpu']}")
    add("")

    add("## 5. 最终 test 评估")
    add("")
    add("> test 集仅在训练与选模**全部结束后**评估一次，未用于挑 epoch 或调参。")
    add("")
    add("| 分组 | 类别数 | 样本数 | Accuracy | Macro-F1 | Weighted-F1 |")
    add("|---|---|---|---|---|---|")
    labels_zh = {
        "all_136": "全部 136 类",
        "original_37": "原有 37 类子集",
        "original_cats_12": "原有 12 猫",
        "original_dogs_25": "原有 25 狗",
        "new_breeds_99": "新增 99 犬种",
    }
    for name in ("all_136", "original_37", "original_cats_12",
                 "original_dogs_25", "new_breeds_99"):
        item = groups.get(name)
        if not item:
            continue
        add(f"| {labels_zh.get(name, name)} | {item['num_classes']} | "
            f"{item['support']:,} | {fmt(item['accuracy'])} | "
            f"{fmt(item['macro_f1'])} | {fmt(item['weighted_f1'])} |")
    add("")

    add("## 6. 重点类别")
    add("")
    add("| 类别 | 说明 | 样本数 | Precision | Recall | F1 |")
    add("|---|---|---|---|---|---|")
    for item in metrics.get("key_breeds", []):
        if not item.get("present"):
            add(f"| `{item['canonical_label']}` | 不在类别中 | — | — | — | — |")
            continue
        add(f"| `{item['canonical_label']}` | {item.get('note', '')} | "
            f"{item['support']} | {fmt(item['precision'])} | "
            f"{fmt(item['recall'])} | {fmt(item['f1'])} |")
    add("")

    worst = metrics.get("worst_new_breeds", [])
    if worst:
        add("新增品种中 F1 最低的 5 类：")
        add("")
        add("| 类别 | 样本数 | F1 |")
        add("|---|---|---|")
        for item in worst:
            add(f"| `{item['canonical_label']}` | {item['support']} | "
                f"{fmt(item['f1'])} |")
        add("")

    # ---- 重点类别混淆去向 ----
    matrix_rows, matrix_labels = load_matrix(model_dir / "confusion_matrix.csv")
    add("### 重点类别的错误去向（真实类别 → 最常被误判成）")
    add("")
    interesting = ("american_pit_bull_terrier",
                   "american_staffordshire_terrier",
                   "border_collie", "collie", "border_terrier")
    for label in interesting:
        pairs = top_confusions(matrix_rows, matrix_labels, label)
        if not pairs:
            add(f"- `{label}`：无样本或无错误")
            continue
        detail = "、".join(f"`{name}`({count})" for name, count in pairs)
        add(f"- `{label}` → {detail}")
    add("")
    add("> AmStaff 与 APBT 是**两个独立类别**，但外观高度相似：")
    add("> 本表中若出现二者互相大量吞并，属\"标签口径正确但视觉可分性低\"的")
    add("> 典型情况，不应通过合并标签来\"改善\"指标。")
    add("")

    add("## 7. 与 V1.1 的可比性说明")
    add("")
    add("V1.1 是 **37 类**模型，V2.1 是 **136 类**模型，两者类别空间不同：")
    add("")
    add("- 不能把两个模型的 overall 指标当作严格同协议下的胜负比较；")
    add("- `original_37` 子集可作为辅助参考，但预测空间从 37 扩展至 136 后，")
    add("  原 37 类的错误去向已发生变化（多了 99 个可被误判的目标），")
    add("  即使同一批图片，指标下降也不必然等价于表征退化；")
    add("- 若要严格比较，需要固定类别空间重训或用拒识机制对齐，属后续任务。")
    add("")

    add("## 8. 已知限制")
    add("")
    add("1. 新增 99 个犬种的训练数据来自 Stanford Dogs（ImageNet 衍生），")
    add("   仅用于本地非商业教育研究，不再分发，需按审核报告引用数据集论文。")
    add("2. 原有 37 类沿用 `data/processed_clean` 的划分；新增品种为本项目自建")
    add("   80/10/10 划分（seed 42），与 Stanford 官方划分不同。")
    add("3. 猫类别仍为原有 12 种（未找到可审核通过的新猫种数据源）。")
    add("4. 单次运行、单一种子（42）；种子敏感性未在本阶段评估。")
    add("5. 本模型为**候选**，未接入后端服务；正式默认仍为 V1.1。")
    add("")

    report_path = model_dir / "V2_1_训练与评估报告.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"[finalize] wrote {model_dir / 'model_version.json'}")
    print(f"[finalize] wrote {history}")
    print(f"[finalize] wrote {report_path}")
    print(f"[finalize] best_model.pth sha256={best_sha}")
    print(f"[finalize] class_names.json sha256={names_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
