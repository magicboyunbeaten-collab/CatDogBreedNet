#!/usr/bin/env python
"""从 coat_predictions_all_splits.csv 单独汇总 **test 划分** 的毛色分组统计。

用法（在仓库根目录执行）::

    python scripts/summarize_coat_test.py

产出 ``coat_color_accuracy_test.csv``（含分子/分母），并在终端打印。
只读已有逐图预测，不重新推理。
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = _REPO_ROOT / "reports" / "v2_1_coat_pitbull_diagnostics"
COAT_ZH = {
    "black_white": "黑白色", "tricolor": "三色", "sable": "貂色",
    "merle": "陨石色", "red_white": "红白/黄白", "other": "其他毛色",
    "uncertain": "待人工复核",
}
COAT_ORDER = ("black_white", "tricolor", "sable", "merle", "red_white",
              "other", "uncertain")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    source = args.out_dir / "coat_predictions_all_splits.csv"
    if not source.exists():
        print(f"[test] 缺少 {source}", file=sys.stderr)
        return 1
    with source.open(encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["split"] == "test"]

    print(f"[test] test 行数 {len(rows)}")
    results = []
    for label in ("collie", "border_collie"):
        other = "border_collie" if label == "collie" else "collie"
        subset_all = [r for r in rows if r["true_label"] == label]
        print()
        print(f"=== {label} test：{len(subset_all)} 张 ===")
        for coat in COAT_ORDER:
            subset = [r for r in subset_all if r["coat"] == coat]
            if not subset:
                results.append({
                    "class": label, "split": "test", "coat": coat,
                    "coat_zh": COAT_ZH[coat], "n": 0, "correct": 0,
                    "accuracy": "", "to_other_class": 0,
                    "other_class_rate": "", "note": "无样本（分母 0）"})
                continue
            correct = sum(int(r["correct"]) for r in subset)
            to_other = sum(1 for r in subset if r["pred_label"] == other)
            wrong = Counter(r["pred_label"] for r in subset
                            if r["pred_label"] != label)
            results.append({
                "class": label, "split": "test", "coat": coat,
                "coat_zh": COAT_ZH[coat], "n": len(subset),
                "correct": correct,
                "accuracy": round(correct / len(subset), 4),
                "to_other_class": to_other,
                "other_class_rate": round(to_other / len(subset), 4),
                "note": ("主要误判目标: "
                         + (wrong.most_common(1)[0][0] if wrong else "无")),
            })
            print(f"  {COAT_ZH[coat]:<8} n={len(subset):>2} "
                  f"correct={correct:>2} acc={correct / len(subset):.3f} "
                  f"-> {other}={to_other}")

    out_path = args.out_dir / "coat_color_accuracy_test.csv"
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["class", "split", "coat",
                                                    "coat_zh", "n", "correct",
                                                    "accuracy",
                                                    "to_other_class",
                                                    "other_class_rate", "note"])
        writer.writeheader()
        writer.writerows(results)
    print()
    print(f"[test] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
