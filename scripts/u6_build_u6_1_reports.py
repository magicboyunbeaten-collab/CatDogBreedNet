#!/usr/bin/env python
"""把 U6.1 的评估明细整理为任务 §10 要求的 ``u6_1_*`` 系列 CSV。

用法（在仓库根目录执行）::

    python scripts/u6_build_u6_1_reports.py

输入：``reports/u6_1_low_lr/u6_baseline_<tag>_{groups,target}.csv``
输出（同目录）：``u6_1_val_group_comparison.csv``、``u6_1_target_metrics.csv``；
并复制 ``u6_per_class_delta.csv`` / ``u6_criteria_check.csv`` /
``u6_multiseed_summary.csv`` 为对应的 ``u6_1_*`` 名称。
"""
from __future__ import annotations

import csv
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports" / "u6_1_low_lr"

#: tag -> 可读名称与是否为多 seed 复核
TAGS: list[tuple[str, str, str]] = [
    ("val", "V2.1 基线（冻结）", "baseline"),
    ("exp06", "exp06 256 分辨率 + 低学习率", "seed 42"),
    ("exp06_seed7", "exp06 256 分辨率 + 低学习率", "seed 7"),
    ("exp06_seed2024", "exp06 256 分辨率 + 低学习率", "seed 2024"),
    ("exp07", "exp07 仅两类颜色扰动 + 低学习率", "seed 42"),
    ("exp08", "exp08 仅两类加权采样 + 低学习率", "seed 42"),
]
GROUPS = ("all_136", "original_37", "new_99")
METRICS = ("accuracy", "macro_f1", "weighted_f1")


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields,
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)

    # ---- 分组对比 ----
    baseline_groups: dict[str, dict[str, float]] = {}
    group_rows: list[dict] = []
    for tag, label, seed in TAGS:
        path = OUT / f"u6_baseline_{tag}_groups.csv"
        if not path.exists():
            print(f"[u6_1] 跳过 {tag}：缺少 {path.name}")
            continue
        rows = {row["group"]: row for row in read_rows(path)}
        row = {"tag": tag, "candidate": label, "seed": seed}
        for group in GROUPS:
            for metric in METRICS:
                value = float(rows[group][metric])
                row[f"{group}_{metric}"] = round(value, 6)
                row[f"{group}_{metric}_n"] = int(rows[group]["n"])
                if tag == "val":
                    baseline_groups[f"{group}_{metric}"] = value
                    row[f"{group}_{metric}_delta"] = 0.0
                else:
                    row[f"{group}_{metric}_delta"] = round(
                        value - baseline_groups[f"{group}_{metric}"], 6)
        group_rows.append(row)
    write_csv(OUT / "u6_1_val_group_comparison.csv", group_rows)
    print(f"[u6_1] wrote u6_1_val_group_comparison.csv（{len(group_rows)} 行）")

    # ---- 目标两类指标 ----
    baseline_target: dict[str, dict] = {}
    target_rows: list[dict] = []
    for tag, label, seed in TAGS:
        path = OUT / f"u6_baseline_{tag}_target.csv"
        if not path.exists():
            continue
        rows = {row["class"]: row for row in read_rows(path)}
        for name in ("collie", "border_collie"):
            row = rows[name]
            item = {
                "tag": tag, "candidate": label, "seed": seed, "class": name,
                "support": int(row["support"]),
                "precision": float(row["precision"]),
                "recall": float(row["recall"]),
                "f1": float(row["f1"]),
                "recall_wilson_low": row["recall_wilson_low"],
                "recall_wilson_high": row["recall_wilson_high"],
                "top_error_destinations": row["top_error_destinations"],
            }
            if tag == "val":
                baseline_target[name] = item
                item["f1_delta_vs_baseline"] = 0.0
            else:
                item["f1_delta_vs_baseline"] = round(
                    item["f1"] - baseline_target[name]["f1"], 6)
            target_rows.append(item)
        bidir = rows["BIDIRECTIONAL"]
        text = bidir["top_error_destinations"]
        c2b = int(text.split("collie->border_collie ", 1)[1].split("/", 1)[0])
        b2c = int(text.split("border_collie->collie ", 1)[1].split("/", 1)[0])
        total = int(text.rsplit("合计 ", 1)[1].split("/", 1)[0])
        denom = int(text.rsplit("/", 1)[1])
        target_rows.append({
            "tag": tag, "candidate": label, "seed": seed,
            "class": "BIDIRECTIONAL",
            "support": int(bidir["support"]),
            "precision": "", "recall": "", "f1": "",
            "recall_wilson_low": "", "recall_wilson_high": "",
            "collie_to_border_collie": c2b,
            "border_collie_to_collie": b2c,
            "bidirectional_total": total,
            "bidirectional_denominator": denom,
            "top_error_destinations": text,
        })
    write_csv(OUT / "u6_1_target_metrics.csv", target_rows)
    print(f"[u6_1] wrote u6_1_target_metrics.csv（{len(target_rows)} 行）")

    # ---- 复制（内容已正确，仅按任务命名）----
    for source, destination in (
        ("u6_per_class_delta.csv", "u6_1_per_class_delta.csv"),
        ("u6_criteria_check.csv", "u6_1_criteria_check.csv"),
        ("u6_multiseed_summary.csv", "u6_1_multiseed_summary.csv"),
    ):
        src = OUT / source
        if src.exists():
            shutil.copyfile(src, OUT / destination)
            print(f"[u6_1] {source} -> {destination}")
        else:
            print(f"[u6_1] 缺少 {source}，跳过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
