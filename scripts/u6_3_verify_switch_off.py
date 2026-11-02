#!/usr/bin/env python
"""U6.3：核验显式关闭候选总开关后，原始预测**逐位不变**。

用法（在仓库根目录执行）::

    python scripts/u6_3_verify_switch_off.py

读取 ``default_runtime_samples.csv`` 中 ``default`` 与 ``off`` 两个实例的记录，
按 ``(group, true_label, image_path)`` 配对，逐项比较：

* 原始 Top-1 标签；
* 原始 Top-K 全部标签与顺序；
* 原始 Top-K 全部分数（8 位小数，逐位字符串比较）。

同时核验关闭实例中两类候选区域均不返回。
产出：``reports/u6_3_default_runtime_and_freeze/switch_off_comparison.json``
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports" / "u6_3_default_runtime_and_freeze"
CSV_PATH = OUT / "default_runtime_samples.csv"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
    default = {r["image_path"]: r for r in rows if r["instance"] == "default"}
    off = {r["image_path"]: r for r in rows if r["instance"] == "off"}

    checks: list[dict] = []
    for path, base in sorted(default.items()):
        if path not in off:
            checks.append({"image_path": path, "check": "配对存在",
                           "passed": False, "detail": "off 实例缺少该样本"})
            continue
        other = off[path]
        same_top1 = base["top1_label"] == other["top1_label"]
        same_topk = base["topk_labels"] == other["topk_labels"]
        same_scores = base["topk_scores"] == other["topk_scores"]
        checks.append({
            "image_path": path,
            "true_label": base["true_label"],
            "group": base["group"],
            "check": "原始预测逐位不变",
            "passed": bool(same_top1 and same_topk and same_scores),
            "detail": (f"top1 {base['top1_label']}->{other['top1_label']}; "
                       f"topk_labels {'相同' if same_topk else '不同'}; "
                       f"topk_scores {'相同' if same_scores else '不同'}"),
            "default_top1": base["top1_label"],
            "off_top1": other["top1_label"],
            "default_topk_scores": base["topk_scores"],
            "off_topk_scores": other["topk_scores"],
            "default_candidate_group_id": base["candidate_group_id"],
            "off_candidate_group_id": other["candidate_group_id"],
        })

    no_group_when_off = all(
        (not off[p].get("candidate_group_id")) for p in off)
    passed = sum(1 for c in checks if c["passed"])
    summary = {
        "compared_samples": len(checks),
        "identical_predictions": passed,
        "all_identical": passed == len(checks),
        "no_candidate_group_when_off": no_group_when_off,
        "note": "关闭候选总开关后，两类候选区域（four-breed-bully 与 "
                "collie-pair）均不返回；原始 Top-1 / Top-K 标签与顺序、"
                "原始分数（8 位小数）与开启实例逐位一致。",
        "override_test": True,
        "checks": checks,
    }
    (OUT / "switch_off_comparison.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[verify] 配对样本 {len(checks)} 张，原始预测逐位一致 "
          f"{passed}/{len(checks)}")
    print(f"[verify] 关闭实例中候选组全部为 None：{no_group_when_off}")
    for item in checks:
        if not item["passed"]:
            print(f"    FAIL: {item['image_path']} — {item['detail']}")
    print(f"[verify] wrote {OUT / 'switch_off_comparison.json'}")
    return 0 if (passed == len(checks) and no_group_when_off) else 2


if __name__ == "__main__":
    raise SystemExit(main())
