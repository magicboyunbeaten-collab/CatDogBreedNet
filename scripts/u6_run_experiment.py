#!/usr/bin/env python
"""U6-C：封装一次边牧专项训练实验（**独立目录、非空拒绝、单一变量**）。

用法（在仓库根目录执行）::

    python scripts/u6_run_experiment.py --exp exp01_pair_color_jitter --seed 42
    python scripts/u6_run_experiment.py --exp exp02_pair_sampler --seed 42
    python scripts/u6_run_experiment.py --exp exp04_resolution --seed 42

设计要点
--------
* 除"本次实验的单一变量"外，**全部超参与 V2.1 基线一致**
  （30 epochs / patience 10 / monitor val_macro_f1 / batch 32 /
  lr 1e-3（head 1e-3, backbone 1e-4）/ wd 1e-4 / StepLR(5, 0.1) / image 224）。
* 每个实验从**同一份冻结的 V2.1 checkpoint** 初始化。
* 产物写入 ``artifacts/v2_2_border_collie_<exp>_seed<seed>/``；
  目录**非空即拒绝启动**（不覆盖、不改名绕过）。
* 训练日志写入 ``reports/u6_border_collie/exp_logs/``，
  汇总追加到 ``u6_experiment_log.csv``。
* **不读 test split**；训练只读 ``data/v2_processed``。
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REPORTS = REPO / "reports" / "u6_border_collie"
ARTIFACTS = REPO / "artifacts"
V21_WEIGHTS = ARTIFACTS / "v2_1_136classes_seed42" / "best_model.pth"
DATA_DIR = REPO / "data" / "v2_processed"
LOG_CSV = REPORTS / "u6_experiment_log.csv"

#: 与 V2.1 基线完全一致的核心超参。
BASELINE_ARGS: list[str] = [
    "--data-dir", str(DATA_DIR),
    "--arch", "resnet18",
    "--epochs", "30",
    "--patience", "10",
    "--monitor", "val_macro_f1",
    "--batch-size", "32",
    "--lr", "1e-3",
    "--lr-head", "1e-3",
    "--lr-backbone", "1e-4",
    "--weight-decay", "1e-4",
    "--step-size", "5",
    "--gamma", "0.1",
    "--augment", "baseline",
    "--image-size", "224",
    "--freeze-strategy", "none",
    "--num-workers", "0",
]

#: U6.1 统一低学习率协议（任务 §3.2）。
#: 说明：`build_optimizer` 在 `lr_head` / `lr_backbone` 均非 None 时，
#: head 与 backbone 的实际学习率**完全由这两个参数决定**，`--lr` 仅作缺省与元数据。
#: 因此这里的 `--lr-head 1e-4 --lr-backbone 5e-5` 即有效学习率；
#: BASELINE_ARGS 中的 `--lr 1e-3 --lr-head 1e-3 --lr-backbone 1e-4` 会被此处覆盖。
LOW_LR_ARGS: list[str] = [
    "--lr-head", "1e-4",
    "--lr-backbone", "5e-5",
]

#: 每个实验的**单一主变量**（以及可读说明）。
#: `image_size` 仅用于评估端提醒，不参与训练命令组装（由 `extra` 决定）。
EXPERIMENTS: dict[str, dict] = {
    "exp01_pair_color_jitter": {
        "variable": "仅对 collie / border_collie 施加温和 ColorJitter",
        "extra": ["--pair-color-jitter", "0.2,0.2,0.3,0.05"],
        "hypothesis": "H1：模型对毛色过拟合，温和颜色扰动可降低该依赖",
    },
    "exp02_pair_sampler": {
        "variable": "仅对 collie / border_collie 加权采样（weight=3.0）",
        "extra": ["--pair-sampler-weight", "3.0"],
        "hypothesis": "H2：目标两类样本偏少，温和加权采样可改善决策边界",
    },
    "exp04_resolution": {
        "variable": "输入分辨率 224 → 256（train 与 eval 同步）",
        "extra": ["--image-size", "256"],
        "hypothesis": "诊断显示细粒度形态区分不足时的独立对照",
    },
    # --- U6.1：统一低学习率协议下的三个对照实验（seed 42）---
    "exp06_resolution256_lowlr": {
        "variable": "输入分辨率 224 → 256（低学习率协议）",
        "extra": ["--image-size", "256"],
        "image_size": 256,
        "low_lr": True,
        "hypothesis": "低学习率下更高输入分辨率可提升细粒度形态区分，"
                      "同时避免 warm-start 被过大更新破坏",
    },
    "exp07_pair_color_jitter_lowlr": {
        "variable": "仅 collie / border_collie 施加温和 ColorJitter（低学习率）",
        "extra": ["--pair-color-jitter", "0.2,0.2,0.3,0.05"],
        "image_size": 224,
        "low_lr": True,
        "hypothesis": "低学习率下颜色扰动可降低毛色依赖（修正 exp01 被"
                      "学习率冲击掩盖的问题）",
    },
    "exp08_pair_sampler_lowlr": {
        "variable": "仅 collie / border_collie 加权采样 weight=3.0（低学习率）",
        "extra": ["--pair-sampler-weight", "3.0"],
        "image_size": 224,
        "low_lr": True,
        "hypothesis": "低学习率下加权采样可改善两类决策边界（修正 exp02 被"
                      "学习率冲击掩盖的问题）",
    },
}


def dir_is_nonempty(path: Path) -> bool:
    return path.exists() and any(path.iterdir())


def append_log(row: dict) -> None:
    LOG_CSV.parent.mkdir(parents=True, exist_ok=True)
    fields = ["exp_id", "seed", "variable", "hypothesis", "started_at",
              "finished_at", "elapsed_seconds", "status", "best_epoch",
              "best_val_macro_f1", "best_val_acc", "output_dir",
              "init_from_sha256", "command"]
    new_file = not LOG_CSV.exists()
    with LOG_CSV.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if new_file:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in fields})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--exp", required=True, choices=sorted(EXPERIMENTS))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    spec = EXPERIMENTS[args.exp]
    out_dir = ARTIFACTS / f"v2_2_border_collie_{args.exp}_seed{args.seed}"
    reports_dir = REPORTS / "exp_logs" / f"{args.exp}_seed{args.seed}"

    if dir_is_nonempty(out_dir):
        print(f"[u6-run] 拒绝启动：输出目录非空 -> {out_dir}", file=sys.stderr)
        print("[u6-run] 请使用新的实验 ID 或清理（本任务不自动清理）。",
              file=sys.stderr)
        return 2

    command = [
        sys.executable, "-m", "ml.train",
        *BASELINE_ARGS,
        "--seed", str(args.seed),
        "--init-from", str(V21_WEIGHTS),
        "--output-dir", str(out_dir),
        "--reports-dir", str(reports_dir),
        *spec["extra"],
    ]
    if spec.get("low_lr"):
        # 追加在 BASELINE_ARGS 之后，覆盖其中的 --lr-head / --lr-backbone
        command.extend(LOW_LR_ARGS)
    print(f"[u6-run] exp={args.exp} seed={args.seed}")
    print(f"[u6-run] variable={spec['variable']}")
    print(f"[u6-run] low_lr_protocol={bool(spec.get('low_lr'))} "
          f"(lr-head=1e-4, lr-backbone=5e-5)")
    print(f"[u6-run] out={out_dir}")
    print(f"[u6-run] cmd={' '.join(command)}")
    if args.dry_run:
        return 0

    started = datetime.now(timezone.utc)
    clock = time.perf_counter()
    reports_dir.mkdir(parents=True, exist_ok=True)
    log_path = reports_dir / "train_stdout.log"
    with log_path.open("w", encoding="utf-8") as log_handle:
        result = subprocess.run(command, cwd=str(REPO), stdout=log_handle,
                                stderr=subprocess.STDOUT, text=True)
    elapsed = time.perf_counter() - clock
    finished = datetime.now(timezone.utc)

    config_path = out_dir / "experiment_config.json"
    best_epoch = best_macro = best_acc = ""
    init_sha = ""
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        best_epoch = config.get("best_epoch", "")
        best_macro = config.get("best_val_macro_f1", "")
        best_acc = config.get("best_val_acc", "")
        init_sha = (config.get("init_from") or {}).get("sha256", "")

    row = {
        "exp_id": args.exp,
        "seed": args.seed,
        "variable": spec["variable"],
        "hypothesis": spec["hypothesis"],
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "status": "ok" if result.returncode == 0 else f"failed({result.returncode})",
        "best_epoch": best_epoch,
        "best_val_macro_f1": best_macro,
        "best_val_acc": best_acc,
        "output_dir": str(out_dir.relative_to(REPO)),
        "init_from_sha256": init_sha,
        "command": " ".join(command),
    }
    append_log(row)
    print(f"[u6-run] status={row['status']} elapsed={elapsed / 60:.1f} min "
          f"best_epoch={best_epoch} best_val_macro_f1={best_macro}")
    print(f"[u6-run] log -> {log_path}")
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
