#!/usr/bin/env python
"""U2 实验矩阵运行器（MODEL_UPGRADE_PLAN.md 的 A2/A3/A4 阶段）。

用法（在仓库根目录执行）::

    python scripts/run_improvement_experiments.py --list
    python scripts/run_improvement_experiments.py --only A2
    python scripts/run_improvement_experiments.py --only A2b_colorjitter,A3a_freeze_layer4
    python scripts/run_improvement_experiments.py            # 全部

设计约束（与 plan.md / CODEBUDDY.md 一致）：
  * 每个实验产物独立存放：``artifacts/exp_<id>/`` 与 ``reports/exp_<id>/``；
  * **不覆盖** ``artifacts/best_model.pth`` 等基线文件；
  * 训练用 train/val 选模；官方 test 集只在实验结束后由 ``ml.evaluate``
    评估**一次**，不参与任何选择；
  * 支持断点续跑：已有完整结果的实验自动跳过；
  * 单个实验失败不影响其余实验，错误记入结果 JSON。

实验矩阵（均以阶段 2 基线配置为基准，一次只改少数变量）：

    A2  数据增强对照   resnet18
    A3  微调策略对照   resnet18
    A4  backbone 对比  resnet50 / convnext_tiny / efficientnet_b0

A1（补充真实数据）与 B（新增类别）需要外部合规图片，不在本脚本范围内。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ml.config import ARTIFACTS_DIR, REPORTS_DIR  # noqa: E402

#: 基线（阶段 2/3）公开指标，仅用于对照展示，不参与任何选择。
BASELINE = {
    "accuracy": 0.8035,
    "macro_f1": 0.8022,
    "weighted_f1": 0.8026,
    "best_val_acc": 0.8401,
    "source": "reports/test_metrics.json（阶段 3，官方 test 集 3669 张）",
}

#: 实验矩阵。``args`` 为追加给 ``python -m ml.train`` 的参数。
EXPERIMENTS: list[dict] = [
    # ---------------- A2：数据增强对照（resnet18，其余同基线） ----------------
    {"id": "A2b_colorjitter", "group": "A2",
     "label": "ColorJitter(0.2, 0.2, 0.2)",
     "args": ["--augment", "+colorjitter"]},
    {"id": "A2c_randomerasing", "group": "A2",
     "label": "RandomErasing(p=0.25)",
     "args": ["--augment", "+randomerasing"]},
    {"id": "A2d_mixup", "group": "A2",
     "label": "Mixup(alpha=0.2)",
     "args": ["--mixup-alpha", "0.2"]},
    # ---------------- A3：微调策略对照（resnet18） ----------------
    {"id": "A3a_freeze_layer4", "group": "A3",
     "label": "解冻 layer4，lr=5e-4",
     "args": ["--freeze-strategy", "layer4", "--lr", "5e-4"]},
    {"id": "A3b_layered_lr", "group": "A3",
     "label": "分层学习率 head 1e-3 / backbone 1e-4",
     "args": ["--lr-head", "1e-3", "--lr-backbone", "1e-4"]},
    {"id": "A3c_label_smoothing", "group": "A3",
     "label": "label smoothing 0.1",
     "args": ["--label-smoothing", "0.1"]},
    {"id": "A3d_epochs20_earlystop", "group": "A3",
     "label": "20 epochs + early stop(patience 3)",
     "args": ["--epochs", "20"]},
    # ---------------- A4：backbone 对比（其余同基线，batch 16） ----------------
    {"id": "A4_resnet50", "group": "A4", "label": "ResNet50",
     "args": ["--arch", "resnet50", "--batch-size", "16"]},
    {"id": "A4_convnext_tiny", "group": "A4", "label": "ConvNeXt-Tiny",
     "args": ["--arch", "convnext_tiny", "--batch-size", "16"]},
    {"id": "A4_efficientnet_b0", "group": "A4", "label": "EfficientNet-B0",
     "args": ["--arch", "efficientnet_b0", "--batch-size", "16"]},
]

RESULTS_DIR = REPORTS_DIR / "exp_results"


def _run(command: list[str], log_path: Path) -> subprocess.CompletedProcess:
    """Run a subcommand, streaming output to the console and a log file."""
    print(f"[exp] $ {' '.join(command)}", flush=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        process = subprocess.run(
            command, cwd=_REPO_ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace")
        log.write(process.stdout or "")
    tail = "\n".join((process.stdout or "").strip().splitlines()[-6:])
    print(f"[exp] exit={process.returncode}\n{tail}", flush=True)
    return process


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - 损坏的 JSON 视为缺失
        return None


def _load_train_log(path: Path) -> dict | None:
    """Summarise the last row of an experiment's train_log.csv."""
    if not path.exists():
        return None
    import csv

    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return None
    last = rows[-1]
    return {
        "final_train_acc": float(last["train_acc"]),
        "final_val_acc": float(last["val_acc"]),
        "final_train_val_gap": round(
            float(last["train_acc"]) - float(last["val_acc"]), 6),
    }


def run_one(experiment: dict, epochs_default: int = 10,
            patience: int = 3, skip_train: bool = False) -> dict:
    """Train (unless skipped) and evaluate one experiment; return its record."""
    exp_id = experiment["id"]
    artifact_dir = ARTIFACTS_DIR / f"exp_{exp_id}"
    reports_dir = REPORTS_DIR / f"exp_{exp_id}"
    train_log = RESULTS_DIR / f"{exp_id}_train.log"
    eval_log = RESULTS_DIR / f"{exp_id}_eval.log"

    record: dict = {
        "id": exp_id,
        "group": experiment["group"],
        "label": experiment["label"],
        "args": experiment["args"],
        "artifact_dir": str(artifact_dir),
        "reports_dir": str(reports_dir),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
    }

    if skip_train:
        # 复用已有 checkpoint（例如修复评估缺陷后只重跑评估）
        weights = artifact_dir / "best_model.pth"
        if not weights.exists():
            record["status"] = "no_checkpoint"
            record["error"] = f"missing {weights}; cannot --skip-train"
            return record
        print(f"[exp] --skip-train: 复用已有 {weights}", flush=True)
        record["train_seconds"] = 0.0
        record["train_returncode"] = 0
    else:
        train_cmd = [
            sys.executable, "-m", "ml.train",
            "--output-dir", str(artifact_dir),
            "--reports-dir", str(reports_dir),
            "--patience", str(patience),
        ] + list(experiment["args"])
        if "--epochs" not in experiment["args"]:
            train_cmd += ["--epochs", str(epochs_default)]

        started = time.time()
        train = _run(train_cmd, train_log)
        record["train_seconds"] = round(time.time() - started, 2)
        record["train_returncode"] = train.returncode
        if train.returncode != 0:
            record["status"] = "train_failed"
            record["error"] = (train.stdout or "")[-2000:]
            return record

    # 官方 test 集：仅此一次最终评估（不再据此调整任何设置）
    eval_cmd = [
        sys.executable, "-m", "ml.evaluate",
        "--weights", str(artifact_dir / "best_model.pth"),
        "--class-names", str(artifact_dir / "class_names.json"),
        "--reports-dir", str(reports_dir),
        "--timed-batches", "20",
        "--e2e-images", "30",
    ]
    started = time.time()
    evaluated = _run(eval_cmd, eval_log)
    record["evaluate_seconds"] = round(time.time() - started, 2)
    record["evaluate_returncode"] = evaluated.returncode
    if evaluated.returncode != 0:
        record["status"] = "evaluate_failed"
        record["error"] = (evaluated.stdout or "")[-2000:]
        return record

    metrics = _load_json(reports_dir / "test_metrics.json")
    if metrics is None:
        record["status"] = "no_metrics"
        record["error"] = f"missing {reports_dir / 'test_metrics.json'}"
        return record

    benchmark = _load_json(reports_dir / "inference_benchmark.json") or {}
    batch_bench = benchmark.get("model_only_batch_benchmark") or {}
    config = _load_json(artifact_dir / "experiment_config.json") or {}
    train_summary = _load_train_log(reports_dir / "train_log.csv") or {}

    record.update({
        "status": "completed",
        "arch": config.get("arch"),
        "augment_preset": config.get("augment_preset"),
        "freeze_strategy": config.get("freeze_strategy"),
        "epochs_completed": config.get("epochs_completed"),
        "best_epoch": config.get("best_epoch"),
        "best_val_acc": config.get("best_val_acc"),
        "final_train_val_gap": train_summary.get("final_train_val_gap"),
        "test_accuracy": metrics.get("accuracy"),
        "test_macro_f1": metrics.get("macro_f1"),
        "test_weighted_f1": metrics.get("weighted_f1"),
        "test_macro_precision": metrics.get("macro_precision"),
        "test_macro_recall": metrics.get("macro_recall"),
        "single_image_latency_ms_mean": (
            batch_bench.get("single_image_latency_ms", {}).get("mean")),
        "throughput_images_per_second": batch_bench.get(
            "throughput_images_per_second"),
        "total_seconds": round(
            record["train_seconds"] + record["evaluate_seconds"], 2),
    })
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the A2/A3/A4 improvement experiment matrix.")
    parser.add_argument("--list", action="store_true",
                        help="list the experiment matrix and exit")
    parser.add_argument("--only", default=None,
                        help="comma-separated experiment ids or groups "
                             "(e.g. 'A2' or 'A2b_colorjitter,A3a_freeze_layer4')")
    parser.add_argument("--epochs", type=int, default=10,
                        help="default epochs for experiments that do not "
                             "override it")
    parser.add_argument("--patience", type=int, default=3)
    parser.add_argument("--force", action="store_true",
                        help="re-run experiments even if a result exists")
    parser.add_argument("--skip-train", action="store_true",
                        help="reuse existing checkpoints and only re-evaluate "
                             "(useful after fixing an evaluation-only defect)")
    args = parser.parse_args(argv)

    if args.list:
        print(f"{'id':<26}{'group':<6}label")
        for exp in EXPERIMENTS:
            print(f"{exp['id']:<26}{exp['group']:<6}{exp['label']}")
        print(f"\n共 {len(EXPERIMENTS)} 个实验；"
              f"基线 Accuracy={BASELINE['accuracy']} "
              f"Macro-F1={BASELINE['macro_f1']}")
        return 0

    selected = EXPERIMENTS
    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        selected = [e for e in EXPERIMENTS
                    if e["id"] in wanted or e["group"] in wanted]
        if not selected:
            print(f"[exp] no experiment matches --only {args.only}")
            return 1

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    for index, experiment in enumerate(selected, 1):
        result_path = RESULTS_DIR / f"{experiment['id']}.json"
        if not args.force:
            existing = _load_json(result_path)
            if existing and existing.get("status") == "completed":
                print(f"[exp] ({index}/{len(selected)}) {experiment['id']} "
                      f"已有完整结果，跳过（--force 可重跑）", flush=True)
                results.append(existing)
                continue

        print("=" * 72, flush=True)
        print(f"[exp] ({index}/{len(selected)}) {experiment['id']} "
              f"[{experiment['group']}] {experiment['label']}", flush=True)
        print(f"[exp] args: {' '.join(experiment['args'])}", flush=True)
        print("=" * 72, flush=True)

        record = run_one(experiment, epochs_default=args.epochs,
                         patience=args.patience, skip_train=args.skip_train)
        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        result_path.write_text(
            json.dumps(record, indent=2, ensure_ascii=False),
            encoding="utf-8")
        results.append(record)
        if record["status"] != "completed":
            print(f"[exp] {experiment['id']} 未完成：{record['status']}"
                  f"（详见 {result_path}）", flush=True)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline": BASELINE,
        "epochs_default": args.epochs,
        "patience": args.patience,
        "completed": sum(1 for r in results if r["status"] == "completed"),
        "total": len(results),
        "experiments": results,
    }
    summary_path = RESULTS_DIR / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[exp] wrote {summary_path}", flush=True)

    # 控制台汇总表
    print("", flush=True)
    print(f"{'id':<26}{'val_acc':>9}{'accuracy':>10}"
          f"{'macroF1':>9}{'weightF1':>10}{'ms/img':>9}{'secs':>8}", flush=True)
    print("-" * 81, flush=True)
    print(f"{'BASELINE (stage2)':<26}{BASELINE['best_val_acc']:>9.4f}"
          f"{BASELINE['accuracy']:>10.4f}{BASELINE['macro_f1']:>9.4f}"
          f"{BASELINE['weighted_f1']:>10.4f}{'':>9}{'':>8}", flush=True)
    for record in results:
        if record.get("status") != "completed":
            print(f"{record['id']:<26}{record.get('status', '?'):>9}", flush=True)
            continue
        latency = record.get("single_image_latency_ms_mean")
        print(f"{record['id']:<26}"
              f"{record.get('best_val_acc', float('nan')):>9.4f}"
              f"{record.get('test_accuracy', float('nan')):>10.4f}"
              f"{record.get('test_macro_f1', float('nan')):>9.4f}"
              f"{record.get('test_weighted_f1', float('nan')):>10.4f}"
              f"{(latency if latency is not None else float('nan')):>9.2f}"
              f"{record.get('total_seconds', 0):>8.0f}", flush=True)
    print("", flush=True)
    print("注意：test 指标为每个实验唯一一次最终评估结果，"
          "未用于任何模型选择；val_acc 为选模依据。", flush=True)
    return 0 if summary["completed"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
