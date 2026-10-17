#!/usr/bin/env python
"""阶段二：多种子配对验证（MODEL_UPGRADE_PLAN 的模型选型前置检查）。

用法（在仓库根目录执行）::

    python scripts/run_seed_validation.py --list
    python scripts/run_seed_validation.py                      # 全部 10 个运行
    python scripts/run_seed_validation.py --only baseline      # 只跑某一配置
    python scripts/run_seed_validation.py --seeds 42,2024      # 自定义种子

比较两个**预先指定**的配置（除学习率策略外完全相同）：

  * ``baseline`` —— 原始 ResNet18 基线配置（全网络 lr=1e-3）
  * ``a3b``      —— 分层学习率（head lr=1e-3 / backbone lr=1e-4）

协议约束（与计划一致）：

  1. 两个配置使用**同一份清洁数据划分**（``--data-dir data/processed_clean``）、
     同一预处理与同一评估命令；
  2. 使用**相同**种子列表做配对实验；
  3. 每运行独立保存配置、权重、训练日志与验证结果；
  4. **每 epoch 按 val_acc 选模**，不按 test 选 epoch/种子/参数；
  5. 每个预计划运行按统一测试协议评估**一次**；test 结果只进最终汇总，
     脚本在设计上"跑完全部运行才生成汇总"，避免事后调参；
  6. 汇总报告每种子 Accuracy / Macro-F1 / Weighted-F1 / 逐类 F1 /
     训练耗时 / 推理延迟，以及均值、标准差与 A3b 相对基线的**配对差值**。

**本脚本不替换任何默认模型**：所有产物写入 ``artifacts/exp_seed_*/``。
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

DEFAULT_SEEDS = [42, 2024, 7, 123, 20261017]
DEFAULT_DATA_DIR = _REPO_ROOT / "data" / "processed_clean"

#: 两个预指定配置。除学习率策略外逐项相同，确保配对差值只反映该变量。
CONFIGS: dict[str, dict] = {
    "baseline": {
        "label": "原始 ResNet18 基线配置（全网络 lr=1e-3）",
        "train_args": [],
    },
    "a3b": {
        "label": "A3b 分层学习率（head 1e-3 / backbone 1e-4）",
        "train_args": ["--lr-head", "1e-3", "--lr-backbone", "1e-4"],
    },
}

#: 两个配置共享的训练超参（单一变量的另一半）。
SHARED = ["--arch", "resnet18", "--augment", "baseline",
          "--freeze-strategy", "none", "--batch-size", "32",
          "--epochs", "10", "--patience", "3"]

RESULTS_DIR = REPORTS_DIR / "seed_validation_results"


def _run(command: list[str], log_path: Path) -> subprocess.CompletedProcess:
    print(f"[seed] $ {' '.join(command)}", flush=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        process = subprocess.run(
            command, cwd=_REPO_ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace")
        log.write(process.stdout or "")
    tail = "\n".join((process.stdout or "").strip().splitlines()[-5:])
    print(f"[seed] exit={process.returncode}\n{tail}", flush=True)
    return process


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def run_one(config_name: str, seed: int, data_dir: Path,
            skip_train: bool = False) -> dict:
    """Train (unless skipped) and evaluate one configuration on one seed."""
    config = CONFIGS[config_name]
    run_id = f"{config_name}_seed{seed}"
    artifact_dir = ARTIFACTS_DIR / f"exp_seed_{run_id}"
    reports_dir = REPORTS_DIR / f"exp_seed_{run_id}"

    record: dict = {
        "run_id": run_id,
        "config": config_name,
        "config_label": config["label"],
        "seed": seed,
        "data_dir": str(data_dir),
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
        print(f"[seed] --skip-train: 复用 {weights}", flush=True)
        record["train_seconds"] = 0.0
    else:
        train_cmd = [
            sys.executable, "-m", "ml.train",
            "--data-dir", str(data_dir),
            "--output-dir", str(artifact_dir),
            "--reports-dir", str(reports_dir),
            "--seed", str(seed),
        ] + SHARED + config["train_args"]
        started = time.time()
        train = _run(train_cmd, RESULTS_DIR / f"{run_id}_train.log")
        record["train_seconds"] = round(time.time() - started, 2)
        record["train_returncode"] = train.returncode
        if train.returncode != 0:
            record["status"] = "train_failed"
            record["error"] = (train.stdout or "")[-2000:]
            return record

    eval_cmd = [
        sys.executable, "-m", "ml.evaluate",
        "--data-dir", str(data_dir),
        "--weights", str(artifact_dir / "best_model.pth"),
        "--class-names", str(artifact_dir / "class_names.json"),
        "--reports-dir", str(reports_dir),
        "--timed-batches", "20",
        "--e2e-images", "30",
    ]
    started = time.time()
    evaluated = _run(eval_cmd, RESULTS_DIR / f"{run_id}_eval.log")
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
    config_json = _load_json(artifact_dir / "experiment_config.json") or {}
    per_class = load_per_class_f1(
        reports_dir / "classification_report.csv",
        class_names=(config_json.get("class_names")
                     or _load_json(artifact_dir / "class_names.json")))

    record.update({
        "status": "completed",
        "arch": config_json.get("arch"),
        "lr": config_json.get("lr"),
        "lr_head": config_json.get("lr_head"),
        "lr_backbone": config_json.get("lr_backbone"),
        "epochs_completed": config_json.get("epochs_completed"),
        "best_epoch": config_json.get("best_epoch"),
        "best_val_acc": config_json.get("best_val_acc"),
        "test_accuracy": metrics.get("accuracy"),
        "test_macro_f1": metrics.get("macro_f1"),
        "test_weighted_f1": metrics.get("weighted_f1"),
        "per_class_f1": per_class,
        "single_image_latency_ms_mean": (
            batch_bench.get("single_image_latency_ms", {}).get("mean")),
        "throughput_images_per_second": batch_bench.get(
            "throughput_images_per_second"),
        "total_seconds": round(
            record["train_seconds"] + record["evaluate_seconds"], 2),
    })
    return record


def load_per_class_f1(path: Path, class_names: list[str] | None = None) -> dict:
    """per-class F1 from an experiment's classification_report.csv.

    ``classification_report.csv`` 末尾带有 ``accuracy`` / ``macro avg`` /
    ``weighted avg`` 三个汇总行，必须过滤掉，否则会混进"逐类"统计。
    """
    if not path.exists():
        return {}
    import csv

    summary_rows = {"accuracy", "macro avg", "weighted avg"}
    with path.open(newline="", encoding="utf-8") as fh:
        rows = {row["class"]: float(row["f1"]) for row in csv.DictReader(fh)}
    if class_names is not None:
        allowed = set(class_names)
        return {k: v for k, v in rows.items() if k in allowed}
    return {k: v for k, v in rows.items() if k not in summary_rows}


def mean_std(values: list[float]) -> tuple[float | None, float | None]:
    clean = [v for v in values if v is not None]
    if not clean:
        return None, None
    mean = sum(clean) / len(clean)
    if len(clean) < 2:
        return mean, None
    variance = sum((v - mean) ** 2 for v in clean) / (len(clean) - 1)
    return mean, variance ** 0.5


def build_summary(results: list[dict]) -> dict:
    """Aggregate per-seed metrics: mean/std and paired A3b - baseline deltas."""
    by_config: dict[str, dict[int, dict]] = {}
    for record in results:
        if record.get("status") != "completed":
            continue
        by_config.setdefault(record["config"], {})[record["seed"]] = record

    summary: dict = {"configs": {}}
    for config_name, runs in sorted(by_config.items()):
        summary["configs"][config_name] = {
            "label": CONFIGS[config_name]["label"],
            "seeds": sorted(runs),
            "n": len(runs),
            "accuracy": dict(zip(("mean", "std"),
                                 mean_std([r["test_accuracy"]
                                           for r in runs.values()]))),
            "macro_f1": dict(zip(("mean", "std"),
                                 mean_std([r["test_macro_f1"]
                                           for r in runs.values()]))),
            "weighted_f1": dict(zip(("mean", "std"),
                                    mean_std([r["test_weighted_f1"]
                                              for r in runs.values()]))),
            "best_val_acc": dict(zip(("mean", "std"),
                                     mean_std([r["best_val_acc"]
                                               for r in runs.values()]))),
            "latency_ms_mean": dict(zip(
                ("mean", "std"),
                mean_std([r["single_image_latency_ms_mean"]
                          for r in runs.values()]))),
            "train_seconds": dict(zip(
                ("mean", "std"),
                mean_std([r["train_seconds"] for r in runs.values()]))),
            "per_run": {str(seed): {
                "accuracy": run["test_accuracy"],
                "macro_f1": run["test_macro_f1"],
                "weighted_f1": run["test_weighted_f1"],
                "best_val_acc": run["best_val_acc"],
                "best_epoch": run["best_epoch"],
                "epochs_completed": run["epochs_completed"],
                "latency_ms_mean": run["single_image_latency_ms_mean"],
                "train_seconds": run["train_seconds"],
            } for seed, run in sorted(runs.items())},
        }

    # 配对差值（只对两配置都完成的种子）
    baseline = by_config.get("baseline", {})
    a3b = by_config.get("a3b", {})
    shared_seeds = sorted(set(baseline) & set(a3b))
    paired: dict = {"seeds": shared_seeds, "n": len(shared_seeds)}
    for metric in ("accuracy", "macro_f1", "weighted_f1"):
        deltas = [a3b[s][f"test_{metric}"] - baseline[s][f"test_{metric}"]
                  for s in shared_seeds]
        mean, std = mean_std(deltas)
        paired[metric] = {
            "deltas": {str(s): round(d, 6) for s, d in zip(shared_seeds,
                                                            deltas)},
            "mean": None if mean is None else round(mean, 6),
            "std": None if std is None else round(std, 6),
            "min": None if not deltas else round(min(deltas), 6),
            "max": None if not deltas else round(max(deltas), 6),
            "all_positive": bool(deltas) and all(d > 0 for d in deltas),
        }
    summary["paired"] = paired

    # 逐类 F1 的配对差值均值（按品种汇总 A3b - baseline）
    if shared_seeds:
        per_class_paired: dict[str, list[float]] = {}
        for seed in shared_seeds:
            base_f1 = baseline[seed]["per_class_f1"]
            a3b_f1 = a3b[seed]["per_class_f1"]
            for breed in set(base_f1) & set(a3b_f1):
                per_class_paired.setdefault(breed, []).append(
                    a3b_f1[breed] - base_f1[breed])
        summary["paired_per_class_f1"] = {
            breed: {"mean_delta": round(sum(v) / len(v), 6), "n": len(v)}
            for breed, v in sorted(per_class_paired.items())}
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Paired multi-seed validation of baseline vs A3b.")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--only", default=None,
                        help="comma-separated config names (baseline,a3b)")
    parser.add_argument("--seeds", default=None,
                        help="comma-separated seed list "
                             f"(default {','.join(map(str, DEFAULT_SEEDS))})")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-train", action="store_true",
                        help="reuse checkpoints and only re-evaluate")
    args = parser.parse_args(argv)

    if args.list:
        for name, config in CONFIGS.items():
            print(f"{name:<10} {config['label']}")
            print(f"           train args: {' '.join(config['train_args']) or '(无)'}")
        print(f"shared:     {' '.join(SHARED)}")
        print(f"seeds:      {DEFAULT_SEEDS}")
        print(f"data-dir:   {args.data_dir}")
        return 0

    seeds = DEFAULT_SEEDS
    if args.seeds:
        seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    configs = list(CONFIGS)
    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        configs = [c for c in configs if c in wanted]
        if not configs:
            print(f"[seed] no config matches --only {args.only}")
            return 1
    if not args.data_dir.is_dir():
        print(f"[seed] 数据目录不存在：{args.data_dir}；"
              f"请先运行 scripts/build_clean_split.py")
        return 1

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    total = len(configs) * len(seeds)
    index = 0
    for config_name in configs:
        for seed in seeds:
            index += 1
            run_id = f"{config_name}_seed{seed}"
            result_path = RESULTS_DIR / f"{run_id}.json"
            if not args.force and not args.skip_train:
                existing = _load_json(result_path)
                if existing and existing.get("status") == "completed":
                    print(f"[seed] ({index}/{total}) {run_id} 已有完整结果，跳过",
                          flush=True)
                    results.append(existing)
                    continue
            print("=" * 72, flush=True)
            print(f"[seed] ({index}/{total}) {run_id} —— "
                  f"{CONFIGS[config_name]['label']}", flush=True)
            print("=" * 72, flush=True)
            record = run_one(config_name, seed, args.data_dir,
                             skip_train=args.skip_train)
            record["finished_at"] = datetime.now(timezone.utc).isoformat()
            result_path.write_text(
                json.dumps(record, indent=2, ensure_ascii=False),
                encoding="utf-8")
            results.append(record)
            if record["status"] != "completed":
                print(f"[seed] {run_id} 未完成：{record['status']}", flush=True)

    # 只有全部运行结束后才生成汇总（避免据 test 做事后调整）
    summary = build_summary(results)
    summary.update({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": str(args.data_dir),
        "seeds": seeds,
        # 注意：键名不能叫 "configs"，那会覆盖 build_summary 产出的统计字典
        "config_names": list(configs),
        "shared_train_args": SHARED,
        "completed": sum(1 for r in results if r["status"] == "completed"),
        "total": total,
        "note": ("test 指标为每个预计划运行的唯一一次最终评估结果，"
                 "未用于任何模型/epoch/种子选择；选模依据是 val_acc。"),
    })
    summary_path = RESULTS_DIR / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[seed] wrote {summary_path}", flush=True)
    print_summary(summary)
    return 0 if summary["completed"] == summary["total"] else 1


def print_summary(summary: dict) -> None:
    print("", flush=True)
    header = (f"{'config':<10}{'metric':<14}{'mean':>10}{'std':>10}"
              f"{'n':>4}")
    print(header, flush=True)
    print("-" * len(header), flush=True)
    for name, data in summary.get("configs", {}).items():
        for metric in ("accuracy", "macro_f1", "weighted_f1"):
            stats = data.get(metric, {})
            print(f"{name:<10}{metric:<14}"
                  f"{stats.get('mean', float('nan')):>10.4f}"
                  f"{(stats.get('std') if stats.get('std') is not None else float('nan')):>10.4f}"
                  f"{data['n']:>4}", flush=True)
    paired = summary.get("paired", {})
    if paired.get("n"):
        print("", flush=True)
        print(f"配对差值（A3b - baseline，n={paired['n']}，"
              f"种子 {paired['seeds']}）", flush=True)
        for metric in ("accuracy", "macro_f1", "weighted_f1"):
            stats = paired[metric]
            print(f"  {metric:<14} mean={stats['mean']:+.4f} "
                  f"std={stats['std']:.4f} range=[{stats['min']:+.4f}, "
                  f"{stats['max']:+.4f}] 全部为正={stats['all_positive']}",
                  flush=True)
    print("", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
