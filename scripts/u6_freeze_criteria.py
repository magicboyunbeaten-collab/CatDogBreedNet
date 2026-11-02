#!/usr/bin/env python
"""U6-A：用实际 val 基线把成功标准换算成绝对阈值并**冻结**。

用法（在仓库根目录执行）::

    python scripts/u6_freeze_criteria.py

若 ``u6_success_criteria.json`` 已存在，脚本**拒绝覆盖**并打印其内容——
保证"训练开始前冻结、之后只读不改"。
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports" / "u6_border_collie"


def read_one(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return next(csv.DictReader(handle))


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    out_path = OUT / "u6_success_criteria.json"
    if out_path.exists():
        print("[freeze] 已存在，拒绝覆盖（冻结后只读）：")
        print(out_path.read_text(encoding="utf-8"))
        return 0

    overall = read_one(OUT / "u6_baseline_val_overall.csv")
    groups = {row["group"]: row for row in read_rows(OUT / "u6_baseline_val_groups.csv")}
    targets = {row["class"]: row for row in read_rows(OUT / "u6_baseline_val_target.csv")}

    collie_f1 = float(targets["collie"]["f1"])
    border_f1 = float(targets["border_collie"]["f1"])
    collie_support = int(targets["collie"]["support"])
    border_support = int(targets["border_collie"]["support"])
    macro_136 = float(groups["all_136"]["macro_f1"])
    macro_37 = float(groups["original_37"]["macro_f1"])
    macro_99 = float(groups["new_99"]["macro_f1"])

    # 双向混淆合计错误数（从 BIDIRECTIONAL 行的文字里解析，避免再算一遍）
    text = targets["BIDIRECTIONAL"]["top_error_destinations"]
    total_errors = int(text.rsplit("合计 ", 1)[1].split("/", 1)[0])

    baseline_sha = hashlib.sha256(
        (OUT / "u6_baseline_val_overall.csv").read_bytes()).hexdigest()

    criteria = {
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "frozen_before_any_training": True,
        "source": "U6-A validation baseline（reports/u6_border_collie/u6_baseline_val_*.csv）",
        "baseline_file_sha256": baseline_sha,
        "val_split": "data/v2_processed/val（2,079 张）",
        "test_split_access_count": 0,
        "baseline": {
            "collie_f1": round(collie_f1, 6),
            "collie_support": collie_support,
            "border_collie_f1": round(border_f1, 6),
            "border_collie_support": border_support,
            "bidirectional_error_count": total_errors,
            "macro_f1_136": round(macro_136, 6),
            "macro_f1_original_37": round(macro_37, 6),
            "macro_f1_new_99": round(macro_99, 6),
            "accuracy_136": float(overall["accuracy"]),
        },
        "thresholds": {
            "collie_f1_min_abs_gain": 0.10,
            "collie_f1_min": round(collie_f1 + 0.10, 6),
            "border_collie_f1_max_drop": 0.02,
            "border_collie_f1_min": round(border_f1 - 0.02, 6),
            "bidirectional_error_min_reduction_ratio": 0.30,
            "bidirectional_error_max":
                int(total_errors * 0.70) if total_errors else 0,
            "macro_f1_136_max_drop": 0.01,
            "macro_f1_136_min": round(macro_136 - 0.01, 6),
            "macro_f1_original_37_max_drop": 0.005,
            "macro_f1_original_37_min": round(macro_37 - 0.005, 6),
            "macro_f1_new_99_max_drop": 0.01,
            "macro_f1_new_99_min": round(macro_99 - 0.01, 6),
            "multiseed_min_consistent_seeds": "2/3",
        },
        "pass_rule": (
            "全部指标同时满足才判定候选合格；任一不满足即 FAIL。"
            "若样本量导致无法合理达标，**不得调低阈值**，应结论为"
            "'现有数据不足以证实改进'并保留 V2.1。"),
        "notes": [
            "collie/border_collie 的 val support 仅 16/15，单个样本即可显著改变 "
            "Recall 与 F1；已同时报告 Wilson 95% 区间。",
            "本阈值文件在任何训练实验产生结果之前写入；后续只读，不因结果不理想而修改。",
            "test split 在 U6-A/U6-C/U6-D 全程未被读取；仅在 U6-E（需人工批准）"
            "才可一次性评估。",
        ],
    }
    out_path.write_text(json.dumps(criteria, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"[freeze] wrote {out_path}")
    print(f"[freeze] collie F1 baseline={collie_f1:.4f} -> min={collie_f1 + 0.10:.4f}")
    print(f"[freeze] border_collie F1 baseline={border_f1:.4f} -> min={border_f1 - 0.02:.4f}")
    print(f"[freeze] 双向错误 baseline={total_errors} -> max={int(total_errors * 0.7)}")
    print(f"[freeze] macro-F1 136 baseline={macro_136:.4f} -> min={macro_136 - 0.01:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
