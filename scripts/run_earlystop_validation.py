#!/usr/bin/env python
"""早停策略（patience）配对对比：A3b 配置下 patience = 3 / 5 / 10。

用法（在仓库根目录执行）::

    python scripts/run_earlystop_validation.py --list
    python scripts/run_earlystop_validation.py --stage train-val        # 阶段一
    python scripts/run_earlystop_validation.py --stage test --patience 5   # 阶段二

设计目标：**把 patience 变成唯一变量**，用**两阶段分离**从流程上杜绝
"依据测试集表现选择 patience"的选择偏差。

- 阶段一 ``--stage train-val``：只训练 + 只做**验证集**评估，
  **完全不读取 test split**；产物含每个种子的最佳 epoch、最佳 val Accuracy、
  val Macro-F1、最终 train/val 差距、实际训练轮数与训练耗时。
- 依据验证集指标选定 patience 并**先记录理由**（见专项报告）。
- 阶段二 ``--stage test --patience N``：仅对被选定的 patience 的 5 个种子
  执行规定的独立 test 评估（复用已训练 checkpoint，**不重训**）。

三组实验除 ``--patience`` 外逐项一致：

- ``--arch resnet18 --augment baseline --freeze-strategy none --batch-size 32``
- ``--lr-head 1e-3 --lr-backbone 1e-4``（A3b 分层学习率）
- ``--step-size 5 --gamma 0.1``（StepLR 不变）、CrossEntropyLoss（无 label
  smoothing）、无 Mixup
- ``--epochs 30``（统一最大轮数上限）、``--data-dir data/processed_clean``
- 种子：42 / 2024 / 7 / 123 / 20261017（三组完全相同）

**本脚本不写任何正式模型路径**：权重一律落 ``artifacts/exp_esp_*``。
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

PATIENCES = [3, 5, 10]
SEEDS = [42, 2024, 7, 123, 20261017]
MAX_EPOCHS = 30
DEFAULT_DATA_DIR = _REPO_ROOT / "data" / "processed_clean"

#: 三组共享的训练参数（不含 patience）。任何一项变更都必须三组同步。
SHARED_TRAIN_ARGS = [
    "--arch", "resnet18",
    "--augment", "baseline",
    "--freeze-strategy", "none",
    "--batch-size", "32",
    "--lr-head", "1e-3",
    "--lr-backbone", "1e-4",
    "--step-size", "5",
    "--gamma", "0.1",
    "--epochs", str(MAX_EPOCHS),
]

RESULTS_DIR = REPORTS_DIR / "earlystop_results"


def _console_print(text: str) -> None:
    """打印可能包含控制台编码无法表示的字符的文本。

    子进程输出用 ``errors="replace"`` 解码，可能含 ``\\ufffd`` 替换字符；
    在 GBK 控制台上直接 print 会抛 UnicodeEncodeError 并使整个运行器崩溃
    （本项目真实发生过：val 评估已成功，运行器却死在打印 tail 上）。
    """
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
    except UnicodeEncodeError:
        text = text.encode(encoding, errors="replace").decode(
            encoding, errors="replace")
    print(text, flush=True)


def _run(command: list[str], log_path: Path) -> subprocess.CompletedProcess:
    print(f"[esp] $ {' '.join(command)}", flush=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        process = subprocess.run(
            command, cwd=_REPO_ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace")
        log.write(process.stdout or "")
    tail = "\n".join((process.stdout or "").strip().splitlines()[-5:])
    _console_print(f"[esp] exit={process.returncode}\n{tail}")
    return process


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _load_train_log(path: Path) -> dict:
    """最后一行的 train/val 表现，用于计算最终 train/val 差距。"""
    if not path.exists():
        return {}
    import csv

    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return {}
    last = rows[-1]
    return {
        "final_epoch": int(last["epoch"]),
        "final_train_acc": float(last["train_acc"]),
        "final_val_acc": float(last["val_acc"]),
        "train_val_gap": round(float(last["train_acc"]) - float(last["val_acc"]),
                               6),
    }


def _load_per_class_f1(csv_path: Path, class_names: list[str]) -> dict:
    if not csv_path.exists():
        return {}
    import csv

    allowed = set(class_names)
    with csv_path.open(newline="", encoding="utf-8") as fh:
        return {row["class"]: float(row["f1"]) for row in csv.DictReader(fh)
                if row["class"] in allowed}


def run_train_val(patience: int, seed: int, data_dir: Path,
                  skip_train: bool = False) -> dict:
    """训练一个运行并做验证集评估；返回结果记录（不触碰 test split）。"""
    run_id = f"p{patience}_seed{seed}"
    artifact_dir = ARTIFACTS_DIR / f"exp_esp_{run_id}"
    reports_dir = REPORTS_DIR / f"exp_esp_{run_id}"
    val_dir = reports_dir / "val_eval"

    record: dict = {
        "run_id": run_id,
        "stage": "train-val",
        "patience": patience,
        "seed": seed,
        "data_dir": str(data_dir),
        "shared_train_args": SHARED_TRAIN_ARGS,
        "max_epochs": MAX_EPOCHS,
        "artifact_dir": str(artifact_dir),
        "reports_dir": str(reports_dir),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
    }

    if skip_train:
        weights = artifact_dir / "best_model.pth"
        if not weights.exists():
            record["status"] = "no_checkpoint"
            record["error"] = f"missing {weights}"
            return record
        print(f"[esp] --skip-train: 复用 {weights}", flush=True)
        record["train_seconds"] = 0.0
    else:
        train_cmd = [
            sys.executable, "-m", "ml.train",
            "--data-dir", str(data_dir),
            "--output-dir", str(artifact_dir),
            "--reports-dir", str(reports_dir),
            "--seed", str(seed),
            "--patience", str(patience),
        ] + SHARED_TRAIN_ARGS
        started = time.time()
        train = _run(train_cmd, RESULTS_DIR / f"{run_id}_train.log")
        record["train_seconds"] = round(time.time() - started, 2)
        record["train_returncode"] = train.returncode
        if train.returncode != 0:
            record["status"] = "train_failed"
            record["error"] = (train.stdout or "")[-2000:]
            return record

    # ---- 训练日志指标（最佳 epoch / 最佳 val acc / 最终 train-val 差距）----
    config = _load_json(artifact_dir / "experiment_config.json") or {}
    log_summary = _load_train_log(reports_dir / "train_log.csv")
    record.update({
        "best_epoch": config.get("best_epoch"),
        "best_val_acc": config.get("best_val_acc"),
        "epochs_completed": config.get("epochs_completed"),
        "epochs_requested": config.get("epochs_requested"),
        "early_stopping_patience": config.get("early_stopping_patience"),
        **log_summary,
    })

    # ---- 验证集评估（仅 val split；不读取 test）----
    eval_cmd = [
        sys.executable, "-m", "ml.evaluate",
        "--data-dir", str(data_dir),
        "--weights", str(artifact_dir / "best_model.pth"),
        "--class-names", str(artifact_dir / "class_names.json"),
        "--split", "val",
        "--no-benchmark",
        "--reports-dir", str(val_dir),
    ]
    started = time.time()
    evaluated = _run(eval_cmd, RESULTS_DIR / f"{run_id}_valeval.log")
    record["val_eval_seconds"] = round(time.time() - started, 2)
    record["val_eval_returncode"] = evaluated.returncode
    if evaluated.returncode != 0:
        record["status"] = "val_eval_failed"
        record["error"] = (evaluated.stdout or "")[-2000:]
        return record

    val_metrics = _load_json(val_dir / "test_metrics.json")
    if val_metrics is None:
        record["status"] = "no_val_metrics"
        record["error"] = f"missing {val_dir / 'test_metrics.json'}"
        return record

    class_names = _load_json(artifact_dir / "class_names.json") or []
    record.update({
        "status": "completed",
        "val_accuracy": val_metrics.get("accuracy"),
        "val_macro_f1": val_metrics.get("macro_f1"),
        "val_weighted_f1": val_metrics.get("weighted_f1"),
        "val_macro_precision": val_metrics.get("macro_precision"),
        "val_macro_recall": val_metrics.get("macro_recall"),
        "val_per_class_f1": _load_per_class_f1(
            val_dir / "classification_report.csv", class_names),
        "total_seconds": round(
            record.get("train_seconds", 0) + record["val_eval_seconds"], 2),
    })
    return record


def run_test_eval(patience: int, seed: int, data_dir: Path) -> dict:
    """仅对已训练完成的 checkpoint 做规定的独立 test 评估。"""
    run_id = f"p{patience}_seed{seed}"
    artifact_dir = ARTIFACTS_DIR / f"exp_esp_{run_id}"
    reports_dir = REPORTS_DIR / f"exp_esp_{run_id}"
    test_dir = reports_dir / "test_eval"

    record: dict = {
        "run_id": run_id,
        "stage": "test",
        "patience": patience,
        "seed": seed,
        "data_dir": str(data_dir),
        "artifact_dir": str(artifact_dir),
        "reports_dir": str(reports_dir),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
    }
    weights = artifact_dir / "best_model.pth"
    if not weights.exists():
        record["status"] = "no_checkpoint"
        record["error"] = f"missing {weights}；请先完成 --stage train-val"
        return record

    eval_cmd = [
        sys.executable, "-m", "ml.evaluate",
        "--data-dir", str(data_dir),
        "--weights", str(weights),
        "--class-names", str(artifact_dir / "class_names.json"),
        "--split", "test",
        "--reports-dir", str(test_dir),
        "--timed-batches", "20",
        "--e2e-images", "30",
    ]
    started = time.time()
    evaluated = _run(eval_cmd, RESULTS_DIR / f"{run_id}_testeval.log")
    record["evaluate_seconds"] = round(time.time() - started, 2)
    record["evaluate_returncode"] = evaluated.returncode
    if evaluated.returncode != 0:
        record["status"] = "evaluate_failed"
        record["error"] = (evaluated.stdout or "")[-2000:]
        return record

    metrics = _load_json(test_dir / "test_metrics.json")
    if metrics is None:
        record["status"] = "no_metrics"
        record["error"] = f"missing {test_dir / 'test_metrics.json'}"
        return record
    benchmark = _load_json(test_dir / "inference_benchmark.json") or {}
    batch_bench = benchmark.get("model_only_batch_benchmark") or {}
    class_names = _load_json(artifact_dir / "class_names.json") or []

    record.update({
        "status": "completed",
        "test_accuracy": metrics.get("accuracy"),
        "test_macro_f1": metrics.get("macro_f1"),
        "test_weighted_f1": metrics.get("weighted_f1"),
        "test_per_class_f1": _load_per_class_f1(
            test_dir / "classification_report.csv", class_names),
        "single_image_latency_ms_mean": (
            batch_bench.get("single_image_latency_ms", {}).get("mean")),
        "throughput_images_per_second": batch_bench.get(
            "throughput_images_per_second"),
    })
    return record


def mean_std(values: list) -> tuple:
    clean = [v for v in values if v is not None]
    if not clean:
        return None, None
    mean = sum(clean) / len(clean)
    if len(clean) < 2:
        return mean, None
    variance = sum((v - mean) ** 2 for v in clean) / (len(clean) - 1)
    return mean, variance ** 0.5


def build_summary(records: list[dict], stage: str) -> dict:
    """按 patience 分组统计 mean/std，并计算相对 patience=3 的配对差值。"""
    by_patience: dict[int, dict[int, dict]] = {}
    for record in records:
        if record.get("status") != "completed":
            continue
        by_patience.setdefault(record["patience"], {})[record["seed"]] = record

    summary: dict = {"stage": stage, "patiences": {}}
    if stage == "train-val":
        fields = ["best_val_acc", "val_accuracy", "val_macro_f1",
                  "val_weighted_f1", "train_val_gap", "epochs_completed",
                  "train_seconds", "total_seconds"]
    else:
        fields = ["test_accuracy", "test_macro_f1", "test_weighted_f1",
                  "single_image_latency_ms_mean",
                  "throughput_images_per_second", "evaluate_seconds"]

    for patience, runs in sorted(by_patience.items()):
        entry: dict = {
            "seeds": sorted(runs),
            "n": len(runs),
            "per_run": {str(seed): {f: run.get(f) for f in fields}
                        for seed, run in sorted(runs.items())},
        }
        for field in fields:
            mean, std = mean_std([run.get(field) for run in runs.values()])
            entry[field] = {"mean": mean, "std": std}
        summary["patiences"][patience] = entry

    # 配对差值：同种子相减，基准为最小的 patience（当前默认 3）
    base_patience = min(by_patience) if by_patience else None
    paired: dict = {"baseline_patience": base_patience, "metrics": {}}
    for patience, runs in sorted(by_patience.items()):
        if base_patience is None or patience == base_patience:
            continue
        base_runs = by_patience[base_patience]
        shared = sorted(set(runs) & set(base_runs))
        for field in fields:
            deltas = [runs[s].get(field) - base_runs[s].get(field)
                      for s in shared]
            if any(d is None for d in deltas):
                continue
            mean, std = mean_std(deltas)
            paired["metrics"].setdefault(field, {})[patience] = {
                "seeds": shared,
                "n": len(shared),
                "deltas": {str(s): round(d, 6)
                           for s, d in zip(shared, deltas)},
                "mean": None if mean is None else round(mean, 6),
                "std": None if std is None else round(std, 6),
                "min": round(min(deltas), 6),
                "max": round(max(deltas), 6),
                "all_positive": all(d > 0 for d in deltas),
            }
    summary["paired_vs_baseline_patience"] = paired
    return summary


def print_summary(summary: dict, stage: str) -> None:
    print("", flush=True)
    fields = (["best_val_acc", "val_accuracy", "val_macro_f1", "val_weighted_f1",
               "train_val_gap", "epochs_completed", "train_seconds"]
              if stage == "train-val" else
              ["test_accuracy", "test_macro_f1", "test_weighted_f1",
               "single_image_latency_ms_mean"])
    header = f"{'patience':>9}" + "".join(f"{f[:16]:>18}" for f in fields)
    print(header, flush=True)
    print("-" * len(header), flush=True)
    for patience, entry in summary.get("patiences", {}).items():
        row = f"{patience:>9}"
        for field in fields:
            stats = entry.get(field, {})
            mean, std = stats.get("mean"), stats.get("std")
            if mean is None:
                row += f"{'N/A':>18}"
            elif std is None:
                row += f"{mean:>18.4f}"
            else:
                row += f"{f'{mean:.4f}±{std:.4f}':>18}"
        print(row, flush=True)

    paired = summary.get("paired_vs_baseline_patience", {})
    base = paired.get("baseline_patience")
    if paired.get("metrics") and base is not None:
        print("", flush=True)
        print(f"配对差值（相对 patience={base}，同种子相减）", flush=True)
        for field, per_patience in paired["metrics"].items():
            for patience, stats in per_patience.items():
                print(f"  patience={patience:<3} {field:<24} "
                      f"mean={stats['mean']:+.4f} std={stats['std']:.4f} "
                      f"range=[{stats['min']:+.4f}, {stats['max']:+.4f}] "
                      f"all_positive={stats['all_positive']} "
                      f"(n={stats['n']})", flush=True)
    print("", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Paired early-stopping patience comparison for A3b.")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--stage", default="train-val",
                        choices=["train-val", "test"])
    parser.add_argument("--patience", type=int, default=None, choices=PATIENCES,
                        help="stage=test 时必填：只评估该 patience 的运行")
    parser.add_argument("--seeds", default=None,
                        help="comma-separated seed list "
                             f"(default {','.join(map(str, SEEDS))})")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-train", action="store_true",
                        help="stage=train-val 时复用已有权重，只补做 val 评估")
    args = parser.parse_args(argv)

    if args.list:
        print("patiences:", PATIENCES, "| seeds:", SEEDS,
              "| max_epochs:", MAX_EPOCHS)
        print("shared train args:", " ".join(SHARED_TRAIN_ARGS))
        print("data dir:", args.data_dir)
        print("stages: train-val (train + val eval only) | "
              "test (test eval for the pre-selected patience)")
        return 0

    if args.stage == "test" and args.patience is None:
        print("[esp] --stage test 必须提供 --patience："
              "test 只能用于评估**预先选定**的配置，不能用来挑 patience")
        return 1

    seeds = SEEDS
    if args.seeds:
        seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    patiences = PATIENCES if args.stage == "train-val" else [args.patience]

    if not args.data_dir.is_dir():
        print(f"[esp] 数据目录不存在：{args.data_dir}；"
              f"请先运行 scripts/build_clean_split.py")
        return 1

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    total = len(patiences) * len(seeds)
    index = 0
    for patience in patiences:
        for seed in seeds:
            index += 1
            run_id = f"p{patience}_seed{seed}"
            result_path = RESULTS_DIR / f"{run_id}.json"
            if args.stage == "train-val" and not args.force \
                    and not args.skip_train:
                existing = _load_json(result_path)
                if existing and existing.get("status") == "completed":
                    print(f"[esp] ({index}/{total}) {run_id} 已有完整结果，跳过",
                          flush=True)
                    records.append(existing)
                    continue
            print("=" * 72, flush=True)
            print(f"[esp] ({index}/{total}) {run_id} —— patience={patience} "
                  f"seed={seed} stage={args.stage}", flush=True)
            print("=" * 72, flush=True)
            if args.stage == "train-val":
                record = run_train_val(patience, seed, args.data_dir,
                                       skip_train=args.skip_train)
            else:
                record = run_test_eval(patience, seed, args.data_dir)
            record["finished_at"] = datetime.now(timezone.utc).isoformat()
            result_path.write_text(
                json.dumps(record, indent=2, ensure_ascii=False),
                encoding="utf-8")
            records.append(record)
            if record["status"] != "completed":
                print(f"[esp] {run_id} 未完成：{record['status']}"
                      f"（详见 {result_path}）", flush=True)

    summary = build_summary(records, args.stage)
    summary.update({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": str(args.data_dir),
        "seeds": seeds,
        "patiences": patiences,
        "max_epochs": MAX_EPOCHS,
        "shared_train_args": SHARED_TRAIN_ARGS,
        "completed": sum(1 for r in records if r["status"] == "completed"),
        "total": total,
        "note": ("stage=train-val 的指标全部来自验证集，用于选择 patience；"
                 "stage=test 只能对预先选定的 patience 运行，"
                 "test 结果不参与任何策略选择。"),
    })
    summary_path = RESULTS_DIR / f"summary_{args.stage}.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[esp] wrote {summary_path}", flush=True)
    print_summary(summary, args.stage)
    return 0 if summary["completed"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
