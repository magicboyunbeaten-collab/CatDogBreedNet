#!/usr/bin/env python
"""APBT 纳入四类相近犬种候选组 —— 离线策略评估（只读，不训练）。

用法（在仓库根目录执行）::

    python scripts/evaluate_apbt_four_group.py
    python scripts/evaluate_apbt_four_group.py --reuse   # 复用已有逐图 CSV

只读取 V2.1 候选 checkpoint 与 **validation split**（``data/v2_processed/val``），
把每张图的**完整 136 维 softmax 概率**（至少 8 位小数）写入
``four_group_validation_predictions.csv``，作为唯一事实源；随后在该文件上派生：

* 当前三类候选组基线（AmStaff / SBT / American Bulldog）重算；
* 四类候选组（+ APBT）定义 B1（沿用 mass 0.30 / margin 0.40）；
* 四类候选组定义 B2 的 validation 阈值网格；
* 六类重点错误清单与三方对比汇总。

**本脚本不 import 正式候选组实现**，策略函数全部自含，因此不会修改
``backend/app/services/candidate_group.py`` 的 ``CANDIDATE_GROUP`` 与阈值，
正式三类行为保持不变。

**禁止事项（代码层面保证）**：本脚本只 ``rglob`` val 目录，不出现任何 test
路径；不训练、不写权重、不改标签、不改数据。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ml.dataset import build_transforms  # noqa: E402
from ml.model import load_checkpoint, resolve_device  # noqa: E402

DEFAULT_MODEL_DIR = _REPO_ROOT / "artifacts" / "v2_1_136classes_seed42"
DEFAULT_VAL_DIR = _REPO_ROOT / "data" / "v2_processed" / "val"
DEFAULT_OUT = _REPO_ROOT / "reports" / "v2_1_apbt_four_breed_candidate_eval"

APBT = "american_pit_bull_terrier"
AMSTAFF = "american_staffordshire_terrier"
SBT = "staffordshire_bull_terrier"
AMBULL = "american_bulldog"

#: 当前正式三类候选组（与 backend/app/services/candidate_group.py 一致，仅用于对照）
THREE_GROUP: tuple[str, ...] = (AMSTAFF, SBT, AMBULL)
#: 本任务评估的四类候选组（APBT + 原三类），成员固定，不随结果调整
FOUR_GROUP: tuple[str, ...] = (APBT, AMSTAFF, SBT, AMBULL)

BREED_ZH = {
    APBT: "美国比特斗牛梗",
    AMSTAFF: "美国斯塔福郡梗",
    SBT: "斯塔福郡斗牛梗",
    AMBULL: "美国斗牛犬",
}

#: B1：沿用当前正式阈值
B1_MASS = 0.30
B1_MARGIN = 0.40

#: B2 阈值网格（仅在 validation split 上比较）
MASS_GRID = (0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)
MARGIN_GRID = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60)

#: U5 验收报告中的三类基线统计（用于差异核对，不用于改阈值）
U5_BASELINE = {
    "val_images": 2079,
    "top1_in_three_group": 36,
    "triggered_three": 5,
    "triggered_true_in_group": 3,
}


# ---------------------------------------------------------------------------
# 策略纯函数（自含，不依赖正式实现）
# ---------------------------------------------------------------------------

def group_stats(probs: dict[str, float],
                members: tuple[str, ...]) -> tuple[float, float]:
    """返回 ``(group_mass, group_margin)``。

    ``group_margin`` = 组内最高原始概率 − 组内第二高原始概率；成员不足两个时
    第二高按 0 计（margin = 最高值）。
    """
    values = sorted((float(probs.get(name, 0.0)) for name in members),
                    reverse=True)
    if not values:
        return 0.0, 0.0
    mass = sum(values)
    margin = values[0] - (values[1] if len(values) > 1 else 0.0)
    return mass, margin


def is_triggered(probs: dict[str, float], top1: str,
                 members: tuple[str, ...], mass_th: float,
                 margin_th: float) -> tuple[bool, str, float, float]:
    """判定触发并返回 ``(triggered, reason, group_mass, group_margin)``。"""
    mass, margin = group_stats(probs, members)
    if top1 not in members:
        return False, "top-1 不在候选组内", mass, margin
    if mass < mass_th:
        return False, (f"候选组总概率 {mass:.4f} 低于阈值 {mass_th:.2f}，"
                       f"模型未在这几个品种间做选择"), mass, margin
    if margin > margin_th:
        return False, (f"组内分差 {margin:.4f} 大于阈值 {margin_th:.2f}，"
                       f"模型已有明确偏好"), mass, margin
    return True, (f"top-1 在候选组内、组内总概率 {mass:.4f} ≥ {mass_th:.2f} "
                  f"且组内分差 {margin:.4f} ≤ {margin_th:.2f}"), mass, margin


def ratio(numerator: int, denominator: int) -> dict:
    """统一的分子/分母/百分比结构，禁止合并成单一分数。"""
    percent = (numerator / denominator * 100) if denominator else None
    return {
        "numerator": numerator,
        "denominator": denominator,
        "percent": (round(percent, 4) if percent is not None else None),
    }


def metrics_for(rows: list[dict], members: tuple[str, ...],
                mass_th: float, margin_th: float) -> dict:
    """一次性算全六类口径（全部带分子/分母）。"""
    member_set = set(members)
    total = len(rows)
    triggered = [row for row in rows
                 if row[f"triggered_{len(members)}"]]
    true_in_group_total = [row for row in rows if row["true_label"] in member_set]

    trig_true_in = sum(1 for row in triggered if row["true_label"] in member_set)
    trig_top1_correct = sum(1 for row in triggered
                            if row["top1_label"] == row["true_label"])
    trig_out = len(triggered) - trig_true_in
    recalled = sum(1 for row in true_in_group_total
                   if row[f"triggered_{len(members)}"])

    apbt_true = [row for row in rows if row["true_label"] == APBT]
    apbt_true_triggered = sum(1 for row in apbt_true
                              if row[f"triggered_{len(members)}"])
    apbt_top1 = [row for row in rows if row["top1_label"] == APBT]
    apbt_top1_triggered = sum(1 for row in apbt_top1
                              if row[f"triggered_{len(members)}"])

    return {
        "candidate_group": list(members),
        "mass_threshold": mass_th,
        "margin_threshold": margin_th,
        "val_images": total,
        "trigger_rate": ratio(len(triggered), total),
        "group_true_label_coverage": ratio(trig_true_in, len(triggered)),
        "member_true_sample_recall": ratio(recalled, len(true_in_group_total)),
        "top1_hit_rate_in_triggered": ratio(trig_top1_correct, len(triggered)),
        "out_of_group_trigger_rate": ratio(trig_out, len(triggered)),
        "member_true_samples": len(true_in_group_total),
        "apbt_true_samples": len(apbt_true),
        "apbt_true_trigger_rate": ratio(apbt_true_triggered, len(apbt_true)),
        "apbt_top1_samples": len(apbt_top1),
        "apbt_top1_trigger_rate": ratio(apbt_top1_triggered, len(apbt_top1)),
    }


# ---------------------------------------------------------------------------
# 推理
# ---------------------------------------------------------------------------

def infer_val(model, val_dir: Path, class_names: list[str], device,
              batch_size: int = 32) -> list[dict]:
    """对 validation split 跑一次前向，保留完整 softmax 向量。"""
    paths = sorted(val_dir.rglob("*.jpg"))
    if not paths:
        raise ValueError(f"no validation images under {val_dir}")
    transform = build_transforms(train=False)
    index_of = {name: i for i, name in enumerate(class_names)}
    for label in FOUR_GROUP:
        if label not in index_of:
            raise ValueError(f"class space lacks candidate label: {label}")

    rows: list[dict] = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(paths), batch_size):
            chunk = paths[start:start + batch_size]
            tensors = []
            for path in chunk:
                with Image.open(path) as image:
                    tensors.append(transform(image.convert("RGB")))
            logits = model(torch.stack(tensors).to(device))
            probs = torch.softmax(logits, dim=1).cpu().numpy()
            for offset, probability in enumerate(probs):
                order = np.argsort(-probability)
                top3 = [(class_names[int(i)], float(probability[int(i)]))
                        for i in order[:3]]
                # 完整 136 维概率，保留 10 位小数（远高于 GPU 跨 batch 噪声）
                full = {name: round(float(probability[index_of[name]]), 10)
                        for name in class_names}
                rows.append({
                    "split": "val",
                    "image_path": str(chunk[offset]),
                    "true_label": chunk[offset].parent.name,
                    "top1_label": top3[0][0],
                    "top1_probability": round(top3[0][1], 10),
                    "top2_label": top3[1][0],
                    "top2_probability": round(top3[1][1], 10),
                    "top3_label": top3[2][0],
                    "top3_probability": round(top3[2][1], 10),
                    "probabilities_json": json.dumps(full, ensure_ascii=False),
                })
    print(f"[eval] inferred {len(rows)} validation images")
    return rows


def load_reuse(path: Path) -> list[dict]:
    """复用已有逐图 CSV，跳过重复推理。"""
    rows = []
    with path.open(encoding="utf-8") as handle:
        for item in csv.DictReader(handle):
            item["top1_probability"] = float(item["top1_probability"])
            item["top2_probability"] = float(item["top2_probability"])
            item["top3_probability"] = float(item["top3_probability"])
            item["probabilities"] = json.loads(item["probabilities_json"])
            rows.append(item)
    print(f"[eval] reused {len(rows)} rows from {path}")
    return rows


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def fmt_ratio(block: dict) -> str:
    if block["denominator"] == 0:
        return "0/0 (分母为 0，无意义)"
    return (f"{block['numerator']}/{block['denominator']} "
            f"({block['percent']:.2f}%)")


def small(block: dict) -> bool:
    return 0 < block["denominator"] < 30


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--val-dir", type=Path, default=DEFAULT_VAL_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--reuse", action="store_true",
                        help="复用已存在的 four_group_validation_predictions.csv")
    args = parser.parse_args(argv)

    out_dir: Path = args.out_dir
    if (out_dir / "four_group_validation_predictions.csv").exists():
        out_dir = out_dir / datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"[eval] target files exist; writing to {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1. 逐图预测（唯一事实源）----
    predictions_csv = out_dir / "four_group_validation_predictions.csv"
    if args.reuse and predictions_csv.exists():
        rows = load_reuse(predictions_csv)
    else:
        device = resolve_device(args.device)
        model, class_names = load_checkpoint(
            args.model_dir / "best_model.pth", device=device)
        if len(class_names) != 136:
            print(f"[eval] expected 136 classes, got {len(class_names)}",
                  file=sys.stderr)
            return 1
        print(f"[eval] device={device} classes={len(class_names)}")
        rows = infer_val(model, args.val_dir, class_names, device)
        slim_fields = ["split", "image_path", "true_label", "top1_label",
                       "top1_probability", "top2_label", "top2_probability",
                       "top3_label", "top3_probability"]
        write_csv(predictions_csv, rows,
                  slim_fields + ["probabilities_json"])
        slim_path = out_dir / "four_group_validation_predictions_slim.csv"
        write_csv(slim_path, rows, slim_fields)
        print(f"[eval] wrote {predictions_csv}")
        print(f"[eval] wrote {slim_path}")
        # CSV 只保留 JSON 字符串；内存中同时保留解析后的 dict 供策略计算。
        for row in rows:
            row["probabilities"] = json.loads(row["probabilities_json"])

    # ---- 2. 三种策略逐图判定 ----
    for row in rows:
        probs = row.get("probabilities") or json.loads(
            row["probabilities_json"])
        t3_mass, t3_margin = group_stats(probs, THREE_GROUP)
        t3_trig, t3_reason, _, _ = is_triggered(
            probs, row["top1_label"], THREE_GROUP, B1_MASS, B1_MARGIN)
        f4_mass, f4_margin = group_stats(probs, FOUR_GROUP)
        f4_trig, f4_reason, _, _ = is_triggered(
            probs, row["top1_label"], FOUR_GROUP, B1_MASS, B1_MARGIN)
        row.update({
            "p_apbt": probs.get(APBT, 0.0),
            "p_amstaff": probs.get(AMSTAFF, 0.0),
            "p_sbt": probs.get(SBT, 0.0),
            "p_ambull": probs.get(AMBULL, 0.0),
            "group_mass_3": round(t3_mass, 10),
            "group_margin_3": round(t3_margin, 10),
            "triggered_3": t3_trig,
            "reason_3": t3_reason,
            "group_mass_4": round(f4_mass, 10),
            "group_margin_4": round(f4_margin, 10),
            "triggered_4": f4_trig,
            "reason_4": f4_reason,
        })

    detail_fields = [
        "split", "image_path", "true_label", "top1_label",
        "top1_probability", "top2_label", "top2_probability",
        "p_apbt", "p_amstaff", "p_sbt", "p_ambull",
        "group_mass_3", "group_margin_3", "triggered_3", "reason_3",
        "group_mass_4", "group_margin_4", "triggered_4", "reason_4",
    ]
    detail_csv = out_dir / "four_group_validation_predictions.csv"
    write_csv(detail_csv, rows, detail_fields)
    print(f"[eval] wrote {detail_csv}（含三类/四类判定）")

    # ---- 3. 三类基线与 U5 报告核对 ----
    total = len(rows)
    top1_in_3 = sum(1 for r in rows if r["top1_label"] in THREE_GROUP)
    trig_3 = [r for r in rows if r["triggered_3"]]
    trig_3_in = sum(1 for r in trig_3 if r["true_label"] in THREE_GROUP)
    trig_3_out = len(trig_3) - trig_3_in
    baseline_check = {
        "val_images": {"now": total, "report": U5_BASELINE["val_images"],
                       "match": total == U5_BASELINE["val_images"]},
        "top1_in_three_group": {"now": top1_in_3,
                                "report": U5_BASELINE["top1_in_three_group"],
                                "match": top1_in_3
                                == U5_BASELINE["top1_in_three_group"]},
        "triggered_three": {"now": len(trig_3),
                            "report": U5_BASELINE["triggered_three"],
                            "match": len(trig_3)
                            == U5_BASELINE["triggered_three"]},
        "triggered_true_in_group": {"now": trig_3_in,
                                    "report": U5_BASELINE[
                                        "triggered_true_in_group"],
                                    "match": trig_3_in
                                    == U5_BASELINE[
                                        "triggered_true_in_group"]},
    }
    print()
    print("[eval] 三类基线与 U5 验收报告核对：")
    for key, item in baseline_check.items():
        flag = "一致" if item["match"] else "**不一致，需调查**"
        print(f"  {key}: 本次 {item['now']} / 报告 {item['report']} -> {flag}")

    # ---- 4. 三方对比汇总 ----
    b1 = metrics_for(rows, FOUR_GROUP, B1_MASS, B1_MARGIN)
    three = metrics_for(rows, THREE_GROUP, B1_MASS, B1_MARGIN)
    summary_rows = [
        {"strategy": "三类基线（当前正式）",
         "candidate_group": "AmStaff;SBT;American Bulldog",
         "mass_threshold": B1_MASS, "margin_threshold": B1_MARGIN,
         **{f"{k}__{sub}": v
            for k, v in three.items() if isinstance(v, dict)
            for sub, v in [("numerator", v["numerator"]),
                           ("denominator", v["denominator"]),
                           ("percent", v["percent"])]}},
        {"strategy": "四类 B1（沿用 0.30/0.40）",
         "candidate_group": "APBT;AmStaff;SBT;American Bulldog",
         "mass_threshold": B1_MASS, "margin_threshold": B1_MARGIN,
         **{f"{k}__{sub}": v
            for k, v in b1.items() if isinstance(v, dict)
            for sub, v in [("numerator", v["numerator"]),
                           ("denominator", v["denominator"]),
                           ("percent", v["percent"])]}},
    ]
    summary_csv = out_dir / "three_vs_four_group_summary.csv"
    all_keys: list[str] = []
    for row in summary_rows:
        for key in row:
            if key not in all_keys:
                all_keys.append(key)
    write_csv(summary_csv, summary_rows, all_keys)
    print(f"[eval] wrote {summary_csv}")

    # ---- 5. B2 阈值网格 ----
    grid_rows = []
    for mass in MASS_GRID:
        for margin in MARGIN_GRID:
            triggered = [r for r in rows
                         if is_triggered(r["probabilities"], r["top1_label"],
                                         FOUR_GROUP, mass, margin)[0]]
            member_set = set(FOUR_GROUP)
            trig_in = sum(1 for r in triggered if r["true_label"] in member_set)
            trig_top1 = sum(1 for r in triggered
                            if r["top1_label"] == r["true_label"])
            trig_out = len(triggered) - trig_in
            true_members = [r for r in rows if r["true_label"] in member_set]
            recalled = sum(1 for r in true_members
                           if is_triggered(r["probabilities"], r["top1_label"],
                                           FOUR_GROUP, mass, margin)[0])
            apbt_true = [r for r in rows if r["true_label"] == APBT]
            apbt_true_trig = sum(
                1 for r in apbt_true
                if is_triggered(r["probabilities"], r["top1_label"],
                                FOUR_GROUP, mass, margin)[0])
            apbt_top1 = [r for r in rows if r["top1_label"] == APBT]
            apbt_top1_trig = sum(
                1 for r in apbt_top1
                if is_triggered(r["probabilities"], r["top1_label"],
                                FOUR_GROUP, mass, margin)[0])
            grid_rows.append({
                "mass_threshold": mass,
                "margin_threshold": margin,
                "triggered_count": len(triggered),
                "trigger_rate_percent": round(len(triggered) / total * 100, 4),
                "group_true_label_coverage": (
                    f"{trig_in}/{len(triggered)} "
                    f"({trig_in / len(triggered) * 100:.2f}%)"
                    if triggered else "0/0 (分母为 0)"),
                "member_true_sample_recall": (
                    f"{recalled}/{len(true_members)} "
                    f"({recalled / len(true_members) * 100:.2f}%)"
                    if true_members else "0/0 (分母为 0)"),
                "top1_hit_rate_in_triggered": (
                    f"{trig_top1}/{len(triggered)} "
                    f"({trig_top1 / len(triggered) * 100:.2f}%)"
                    if triggered else "0/0 (分母为 0)"),
                "out_of_group_trigger_count": trig_out,
                "out_of_group_trigger_rate": (
                    f"{trig_out}/{len(triggered)} "
                    f"({trig_out / len(triggered) * 100:.2f}%)"
                    if triggered else "0/0 (分母为 0)"),
                "apbt_true_triggered": f"{apbt_true_trig}/{len(apbt_true)}",
                "apbt_top1_triggered": f"{apbt_top1_trig}/{len(apbt_top1)}",
            })
    grid_csv = out_dir / "four_group_threshold_grid.csv"
    write_csv(grid_csv, grid_rows, list(grid_rows[0].keys()))
    print(f"[eval] wrote {grid_csv}（{len(grid_rows)} 组合）")

    # ---- 6. B2 建议阈值（可解释规则）----
    b1_recall = b1["member_true_sample_recall"]["numerator"]
    b1_out = b1["out_of_group_trigger_rate"]["numerator"]
    candidates = [row for row in grid_rows
                  if int(row["member_true_sample_recall"].split("/")[0])
                  >= b1_recall
                  and row["out_of_group_trigger_count"] <= b1_out]
    chosen = max(candidates, key=lambda row: row["triggered_count"]) \
        if candidates else None
    if chosen:
        print()
        print(f"[eval] B2 建议阈值: mass>={chosen['mass_threshold']} "
              f"margin<={chosen['margin_threshold']}  触发 "
              f"{chosen['triggered_count']} 张，召回 "
              f"{chosen['member_true_sample_recall']}，组外误触发 "
              f"{chosen['out_of_group_trigger_count']} 张")
    else:
        print()
        print("[eval] B2 无满足约束的组合 → 建议维持 B1 保守规则")

    # ---- 7. 重点错误清单 ----
    newly = [r for r in rows if r["triggered_4"] and not r["triggered_3"]]
    both = [r for r in rows if r["triggered_4"] and r["triggered_3"]]
    out_of_group = [r for r in rows
                    if (r["triggered_4"] or r["triggered_3"])
                    and r["true_label"] not in FOUR_GROUP]
    apbt_conf = [r for r in rows
                 if r["true_label"] == APBT and r["top1_label"] in THREE_GROUP]
    amstaff_conf = [r for r in rows
                    if r["true_label"] == AMSTAFF
                    and r["top1_label"] in (APBT, SBT, AMBULL)]
    sbt_ambull_conf = [r for r in rows
                       if r["true_label"] in (SBT, AMBULL)
                       and r["top1_label"] in FOUR_GROUP
                       and r["top1_label"] != r["true_label"]]
    apbt_top1_competitive = [
        r for r in rows
        if r["top1_label"] == APBT and r["group_margin_4"] <= B1_MARGIN]

    write_csv(out_dir / "newly_triggered_by_apbt.csv", newly,
              detail_fields)
    write_csv(out_dir / "triggered_by_both_strategies.csv", both, detail_fields)
    write_csv(out_dir / "out_of_group_trigger_examples.csv", out_of_group,
              detail_fields)
    write_csv(out_dir / "apbt_related_confusions.csv",
              apbt_conf + amstaff_conf + sbt_ambull_conf + apbt_top1_competitive,
              detail_fields)
    print(f"[eval] newly_triggered_by_apbt.csv {len(newly)} 行；"
          f"triggered_by_both {len(both)} 行；"
          f"out_of_group {len(out_of_group)} 行；"
          f"apbt_related_confusions "
          f"{len(apbt_conf) + len(amstaff_conf) + len(sbt_ambull_conf) + len(apbt_top1_competitive)} 行")

    # ---- 8. 汇总 JSON ----
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_dir": str(args.model_dir),
        "val_dir": str(args.val_dir),
        "split_used": "validation only (test split never read)",
        "test_split_access_count": 0,
        "val_images": total,
        "three_group": three,
        "four_group_b1": b1,
        "four_group_b2_recommended": chosen,
        "baseline_check_vs_u5_report": baseline_check,
        "counts": {
            "top1_in_three_group": top1_in_3,
            "top1_in_four_group": sum(1 for r in rows
                                      if r["top1_label"] in FOUR_GROUP),
            "top1_is_apbt": sum(1 for r in rows
                                if r["top1_label"] == APBT),
            "triggered_three": len(trig_3),
            "triggered_three_true_in_group": trig_3_in,
            "triggered_three_out_of_group": trig_3_out,
            "triggered_four_b1": sum(1 for r in rows if r["triggered_4"]),
            "newly_triggered_by_apbt": len(newly),
            "triggered_by_both": len(both),
            "out_of_group_triggered": len(out_of_group),
            "apbt_true_to_three_group": len(apbt_conf),
            "amstaff_true_to_apbt_sbt_ambull": len(amstaff_conf),
            "sbt_ambull_true_to_four_group": len(sbt_ambull_conf),
            "apbt_top1_competitive": len(apbt_top1_competitive),
            "member_true_samples": sum(1 for r in rows
                                       if r["true_label"] in FOUR_GROUP),
            "member_true_breakdown": dict(Counter(
                r["true_label"] for r in rows if r["true_label"] in FOUR_GROUP)),
        },
    }
    json_path = out_dir / "evaluation_summary.json"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    print(f"[eval] wrote {json_path}")
    print()
    print(f"[eval] 三类触发 {len(trig_3)}/{total} "
          f"({len(trig_3) / total * 100:.2f}%)；"
          f"四类 B1 触发 {summary['counts']['triggered_four_b1']}/{total} "
          f"({summary['counts']['triggered_four_b1'] / total * 100:.2f}%)；"
          f"新增 {len(newly)} 张")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
