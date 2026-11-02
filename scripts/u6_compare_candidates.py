#!/usr/bin/env python
"""U6-D：用**同一 val 与同一评估口径**比较候选与 V2.1 基线，并按冻结标准判定。

用法（在仓库根目录执行）::

    # 先对每个候选跑一次 u6_baseline_val.py --weights <exp>/best_model.pth --tag exp01
    python scripts/u6_compare_candidates.py --tags exp01 exp02 exp04

    # 多 seed 复核（同一候选的三个 seed）
    python scripts/u6_compare_candidates.py --tags exp01 \
        --multiseed exp01_pair_color_jitter=exp01,exp01_seed7,exp01_seed2024

产出（``reports/u6_border_collie/``）：

* ``u6_val_comparison_136_classes.csv`` —— 136/37/99 三组指标 + 与基线差值
* ``u6_per_class_delta.csv`` —— 136 类逐类 F1 变化、support、退化排序
* ``u6_target_confusion_change.csv`` —— 两类双向混淆计数与率的变化
* ``u6_criteria_check.csv`` —— 冻结标准逐条 PASS/FAIL
* ``u6_multiseed_summary.csv`` —— 多 seed 均值/标准差/方向一致性

**只读** CSV；不改任何权重、数据或既有报告。
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports" / "u6_border_collie"
TARGETS = ("collie", "border_collie")


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"missing {path}")
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
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


def per_class_metrics(predictions: list[dict], class_names: list[str]) -> dict:
    """从逐图预测直接算每类 P/R/F1/support（无需重跑模型）。"""
    from sklearn.metrics import precision_recall_fscore_support

    index_of = {name: i for i, name in enumerate(class_names)}
    y_true = [index_of[r["true_label"]] for r in predictions]
    y_pred = [index_of[r["pred_label"]] for r in predictions]
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=list(range(len(class_names))),
        average=None, zero_division=0)
    return {
        name: {
            "precision": float(precision[i]),
            "recall": float(recall[i]),
            "f1": float(f1[i]),
            "support": int(support[i]),
        }
        for i, name in enumerate(class_names)
    }


def wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 1.0)
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5) \
        / denominator
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def bidirectional(predictions: list[dict]) -> dict:
    pred_map = {r["image_path"]: r for r in predictions}
    c2b = sum(1 for r in predictions
              if r["true_label"] == "collie"
              and r["pred_label"] == "border_collie")
    b2c = sum(1 for r in predictions
              if r["true_label"] == "border_collie"
              and r["pred_label"] == "collie")
    c_total = sum(1 for r in predictions if r["true_label"] == "collie")
    b_total = sum(1 for r in predictions
                  if r["true_label"] == "border_collie")
    c_correct = sum(1 for r in predictions if r["true_label"] == "collie"
                    and r["pred_label"] == "collie")
    b_correct = sum(1 for r in predictions
                    if r["true_label"] == "border_collie"
                    and r["pred_label"] == "border_collie")
    c_low, c_high = wilson(c_correct, c_total)
    b_low, b_high = wilson(b_correct, b_total)
    return {
        "collie_to_border_collie": c2b,
        "border_collie_to_collie": b2c,
        "bidirectional_total": c2b + b2c,
        "collie_total": c_total,
        "border_collie_total": b_total,
        "collie_recall": round(c_correct / c_total, 4) if c_total else "",
        "border_collie_recall":
            round(b_correct / b_total, 4) if b_total else "",
        "collie_recall_wilson": f"[{c_low:.3f}, {c_high:.3f}]",
        "border_collie_recall_wilson": f"[{b_low:.3f}, {b_high:.3f}]",
        "sample_count_consistent": len(pred_map),
    }


def criteria_check(tag: str, groups: dict, targets: dict,
                   criteria: dict) -> list[dict]:
    base = criteria["baseline"]
    thr = criteria["thresholds"]
    rows = []
    collie_f1 = float(targets["collie"]["f1"])
    border_f1 = float(targets["border_collie"]["f1"])
    bidir_text = targets["BIDIRECTIONAL"]["top_error_destinations"]
    bidir = int(bidir_text.rsplit("合计 ", 1)[1].split("/", 1)[0])

    def add(name: str, value, threshold, passed: bool, note: str = "") -> None:
        rows.append({
            "tag": tag,
            "criterion": name,
            "observed": value,
            "threshold": threshold,
            "result": "PASS" if passed else "FAIL",
            "note": note,
        })

    add("collie_f1", round(collie_f1, 4), f">= {thr['collie_f1_min']:.4f}",
        collie_f1 >= thr["collie_f1_min"] - 1e-9,
        f"baseline {base['collie_f1']:.4f}; support {base['collie_support']}")
    add("border_collie_f1", round(border_f1, 4),
        f">= {thr['border_collie_f1_min']:.4f}",
        border_f1 >= thr["border_collie_f1_min"] - 1e-9,
        f"baseline {base['border_collie_f1']:.4f}; support "
        f"{base['border_collie_support']}")
    add("bidirectional_error_count", bidir,
        f"<= {thr['bidirectional_error_max']}",
        bidir <= thr["bidirectional_error_max"],
        f"baseline {base['bidirectional_error_count']}")
    add("macro_f1_136", round(float(groups["all_136"]["macro_f1"]), 4),
        f">= {thr['macro_f1_136_min']:.4f}",
        float(groups["all_136"]["macro_f1"]) >= thr["macro_f1_136_min"] - 1e-9,
        f"baseline {base['macro_f1_136']:.4f}")
    add("macro_f1_original_37",
        round(float(groups["original_37"]["macro_f1"]), 4),
        f">= {thr['macro_f1_original_37_min']:.4f}",
        float(groups["original_37"]["macro_f1"])
        >= thr["macro_f1_original_37_min"] - 1e-9,
        f"baseline {base['macro_f1_original_37']:.4f}")
    add("macro_f1_new_99", round(float(groups["new_99"]["macro_f1"]), 4),
        f">= {thr['macro_f1_new_99_min']:.4f}",
        float(groups["new_99"]["macro_f1"])
        >= thr["macro_f1_new_99_min"] - 1e-9,
        f"baseline {base['macro_f1_new_99']:.4f}")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tags", nargs="+", required=True,
                        help="候选 tag 列表（对应 u6_baseline_<tag>_*.csv）")
    parser.add_argument("--baseline-tag", default="val")
    parser.add_argument("--out-dir", type=Path, default=OUT,
                        help="报告输出目录（默认 reports/u6_border_collie，"
                             "向后兼容；U6.1 传 reports/u6_1_low_lr）")
    parser.add_argument("--eval-dir", type=Path, default=OUT,
                        help="评估 CSV 输入目录（默认与 --out-dir 相同）")
    parser.add_argument("--criteria", type=Path,
                        default=REPO / "reports/u6_border_collie"
                        / "u6_success_criteria.json",
                        help="冻结成功标准 JSON（只读，不得复制后修改）")
    parser.add_argument("--multiseed", default=None,
                        help="name=tag1,tag2,tag3 —— 同一候选的多 seed 复核")
    args = parser.parse_args(argv)

    criteria = json.loads(Path(args.criteria).read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    eval_dir = Path(args.eval_dir)
    baseline_preds = read_rows(
        eval_dir / f"u6_baseline_{args.baseline_tag}_predictions.csv")
    baseline_groups = {row["group"]: row for row in
                       read_rows(eval_dir / f"u6_baseline_{args.baseline_tag}_groups.csv")}
    baseline_targets = {row["class"]: row for row in
                        read_rows(eval_dir / f"u6_baseline_{args.baseline_tag}_target.csv")}
    class_names = sorted({r["true_label"] for r in baseline_preds}
                         | {r["pred_label"] for r in baseline_preds})
    # 用真实类别全集（从 groups 无法得到 136 类名，故从 predictions 的 top5 补不全；
    # 逐类指标只需要出现在预测里的类别，缺失类别 support 为 0，不影响 delta 结论）
    baseline_per_class = per_class_metrics(baseline_preds, class_names)
    baseline_bidir = bidirectional(baseline_preds)

    comparison: list[dict] = []
    deltas: list[dict] = []
    confusions: list[dict] = [
        {"tag": "BASELINE", **baseline_bidir},
    ]
    checks: list[dict] = []

    def add_comparison(tag: str, groups: dict) -> None:
        row = {"tag": tag}
        for group in ("all_136", "original_37", "new_99"):
            for metric in ("accuracy", "macro_f1", "weighted_f1"):
                row[f"{group}_{metric}"] = float(groups[group][metric])
                row[f"{group}_{metric}_delta"] = round(
                    float(groups[group][metric])
                    - float(baseline_groups[group][metric]), 6)
        comparison.append(row)

    add_comparison("BASELINE", baseline_groups)

    for tag in args.tags:
        pred_path = eval_dir / f"u6_baseline_{tag}_predictions.csv"
        if not pred_path.exists():
            print(f"[u6d] 跳过 {tag}：缺少 {pred_path.name}（需先跑 "
                  f"u6_baseline_val.py --tag {tag}）", file=sys.stderr)
            continue
        preds = read_rows(pred_path)
        if len(preds) != len(baseline_preds):
            raise ValueError(f"{tag} 样本数 {len(preds)} 与基线 "
                             f"{len(baseline_preds)} 不一致，无法公平比较")
        groups = {row["group"]: row for row in
                  read_rows(eval_dir / f"u6_baseline_{tag}_groups.csv")}
        targets = {row["class"]: row for row in
                   read_rows(eval_dir / f"u6_baseline_{tag}_target.csv")}

        add_comparison(tag, groups)
        confusions.append({"tag": tag, **bidirectional(preds)})
        checks.extend(criteria_check(tag, groups, targets, criteria))

        candidate_per_class = per_class_metrics(preds, class_names)
        for name in class_names:
            base = baseline_per_class[name]
            cand = candidate_per_class[name]
            deltas.append({
                "tag": tag,
                "class": name,
                "support": base["support"],
                "baseline_f1": round(base["f1"], 4),
                "candidate_f1": round(cand["f1"], 4),
                "delta_f1": round(cand["f1"] - base["f1"], 4),
                "baseline_recall": round(base["recall"], 4),
                "candidate_recall": round(cand["recall"], 4),
                "is_target_pair": "yes" if name in TARGETS else "no",
            })

    write_csv(out_dir / "u6_val_comparison_136_classes.csv", comparison)
    write_csv(out_dir / "u6_per_class_delta.csv", deltas)
    write_csv(out_dir / "u6_target_confusion_change.csv", confusions)
    write_csv(out_dir / "u6_criteria_check.csv", checks)

    # ---- 多 seed 汇总 ----
    if args.multiseed:
        name, tag_list = args.multiseed.split("=", 1)
        tags = [t.strip() for t in tag_list.split(",") if t.strip()]
        rows = []
        for metric in ("macro_f1", "accuracy", "weighted_f1"):
            for group in ("all_136", "original_37", "new_99"):
                values = [g[group][metric] for g in
                          ({row["group"]: row for row in read_rows(
                              eval_dir / f"u6_baseline_{t}_groups.csv")}
                           for t in tags)]
                values = [float(v) for v in values]
                rows.append({
                    "candidate": name,
                    "metric": f"{group}_{metric}",
                    "n_seeds": len(values),
                    "mean": round(statistics.mean(values), 6),
                    "stdev": round(statistics.pstdev(values), 6) if len(values) > 1 else 0.0,
                    "min": round(min(values), 6),
                    "max": round(max(values), 6),
                    "per_seed": ";".join(f"{t}:{v:.6f}"
                                         for t, v in zip(tags, values)),
                })
        # 目标类 F1 的跨 seed 一致性
        for label in TARGETS:
            values = []
            for t in tags:
                targets = {row["class"]: row for row in
                           read_rows(eval_dir / f"u6_baseline_{t}_target.csv")}
                values.append(float(targets[label]["f1"]))
            baseline_value = float(baseline_targets[label]["f1"])
            improved = sum(1 for v in values if v > baseline_value)
            rows.append({
                "candidate": name,
                "metric": f"{label}_f1",
                "n_seeds": len(values),
                "mean": round(statistics.mean(values), 6),
                "stdev": round(statistics.pstdev(values), 6) if len(values) > 1 else 0.0,
                "min": round(min(values), 6),
                "max": round(max(values), 6),
                "per_seed": ";".join(f"{t}:{v:.6f}"
                                     for t, v in zip(tags, values)),
                "baseline": round(baseline_value, 6),
                "seeds_improved": f"{improved}/{len(values)}",
                "direction_consistent": "yes" if improved * 3 >= len(values) * 2
                                        else "no",
            })
        write_csv(out_dir / "u6_multiseed_summary.csv", rows)
        print(f"[u6d] 多 seed 汇总：{name}（{len(tags)} 个 seed）")

    # ---- 控制台小结 ----
    print()
    print(f"[u6d] baseline 双向错误 {baseline_bidir['bidirectional_total']}"
          f"（collie->border {baseline_bidir['collie_to_border_collie']} / "
          f"border->collie {baseline_bidir['border_collie_to_collie']}）")
    for row in comparison[1:]:
        print(f"[u6d] {row['tag']:<28} "
              f"macroF1_136={row['all_136_macro_f1']:.6f} "
              f"(Δ{row['all_136_macro_f1_delta']:+.4f}) "
              f"37={row['original_37_macro_f1']:.6f} "
              f"(Δ{row['original_37_macro_f1_delta']:+.4f}) "
              f"99={row['new_99_macro_f1']:.6f} "
              f"(Δ{row['new_99_macro_f1_delta']:+.4f})")
    if checks:
        print()
        for tag in {row["tag"] for row in checks}:
            tag_rows = [row for row in checks if row["tag"] == tag]
            passed = sum(1 for row in tag_rows if row["result"] == "PASS")
            print(f"[u6d] {tag}: {passed}/{len(tag_rows)} 条冻结标准通过")
            for row in tag_rows:
                if row["result"] == "FAIL":
                    print(f"        FAIL {row['criterion']}: "
                          f"observed={row['observed']} {row['threshold']}")
    print(f"[u6d] wrote comparison / per_class / confusion / criteria")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
