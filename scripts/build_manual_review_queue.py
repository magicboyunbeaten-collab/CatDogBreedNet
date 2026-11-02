#!/usr/bin/env python
"""生成人工复核队列 ``manual_review_queue.csv``（只列出，不下结论）。

用法（在仓库根目录执行）::

    python scripts/build_manual_review_queue.py

数据来源（均由前序诊断脚本产出）：

* ``all_predictions_136.csv`` / ``old37_predicted_as_new99.csv`` — 逐图预测；
* ``apbt_amstaff_cross_class_duplicate_pairs.csv`` — 可疑重复配对。

优先级：

1. APBT ↔ AmStaff 双向互相误判；
2. APBT → Staffordshire Bull Terrier / American Bulldog / Bullmastiff；
3. APBT / AmStaff 及相关类别间的跨类别 MD5 / pHash 可疑匹配；
4. 原有 37 类被判为新增品种；
5. ``collie`` ↔ ``border_collie`` 互相混淆。

``review_status`` 一律留空——本脚本**不**给出"错标/正确"结论。
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

OUT_DIR = _REPO_ROOT / "reports" / "v2_1_diagnostics"
OUT_NAME = "manual_review_queue.csv"

FIELDNAMES = ["priority", "priority_reason", "sample_id", "true_label",
              "pred_label", "top1_prob", "top2_label", "top2_prob", "top5",
              "split", "image_path", "source_evidence", "review_status",
              "review_notes"]

APBT = "american_pit_bull_terrier"
AMSTAFF = "american_staffordshire_terrier"
APBT_SIDE = {"staffordshire_bull_terrier", "american_bulldog",
             "bull_mastiff"}


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        print(f"[queue] 缺少 {path}，跳过该来源", file=sys.stderr)
        return []
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--in-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    in_dir: Path = args.in_dir
    predictions = read_csv(in_dir / "all_predictions_136.csv")
    old37_new = read_csv(in_dir / "old37_predicted_as_new99.csv")
    duplicates = read_csv(in_dir / "apbt_amstaff_cross_class_duplicate_pairs.csv")

    if not predictions:
        print("[queue] all_predictions_136.csv 是必需输入，停止",
              file=sys.stderr)
        return 1

    by_id = {row["sample_id"]: row for row in predictions}
    queue: list[dict] = []

    def push(priority: int, reason: str, source: dict, notes: str) -> None:
        queue.append({
            "priority": priority,
            "priority_reason": reason,
            "sample_id": source.get("sample_id", ""),
            "true_label": source.get("true_label", ""),
            "pred_label": source.get("pred_label", ""),
            "top1_prob": source.get("top1_prob", ""),
            "top2_label": source.get("top2_label", ""),
            "top2_prob": source.get("top2_prob", ""),
            "top5": source.get("top5", ""),
            "split": source.get("split", ""),
            "image_path": source.get("image_path", ""),
            "source_evidence": source.get("source_evidence", ""),
            "review_status": "",
            "review_notes": notes,
        })

    # 优先级 1：APBT <-> AmStaff 双向互误
    for row in predictions:
        if (row["true_label"] == APBT and row["pred_label"] == AMSTAFF) or (
                row["true_label"] == AMSTAFF and row["pred_label"] == APBT):
            push(1, "APBT<->AmStaff 双向互误", row,
                 "核对外观与耳型/体格；确认来源标签是否可能跨品种混用；"
                 "不得仅凭模型预测改标签")

    # 优先级 2：APBT -> SBT / American Bulldog / Bullmastiff
    for row in predictions:
        if row["true_label"] == APBT and row["pred_label"] in APBT_SIDE:
            push(2, f"APBT->{row['pred_label']}", row,
                 "同类 bully 犬外观相近，核对耳型/头骨/体型与来源标注")

    # 优先级 3：跨类别可疑匹配（每对拆成两行，A/B 各一）
    for pair in duplicates:
        for side, other in (("a", "b"), ("b", "a")):
            # 按绝对路径匹配预测行（路径字段与诊断脚本输出一致）
            match = next((row for row in predictions
                          if row["image_path"] == pair[f"path_{side}"]), None)
            if match is None:
                continue
            push(3, f"跨类别可疑重复({pair['pair_type']})", match,
                 f"与 {pair[f'class_{other}']} / {pair[f'split_{other}']} 的 "
                 f"`{Path(pair[f'path_{other}']).name}` 相似："
                 f"md5_equal={pair['md5_equal']} "
                 f"pHash={pair['phash_distance']}；不自动删除、不自动判定")

    # 优先级 4：原 37 类被判为新增品种
    for row in old37_new:
        push(4, "原有 37 类被判为新增品种", row,
             "检查是否为相似品种（如梗类/猎犬），以及新增类别是否过度吸引")

    # 优先级 5：collie <-> border_collie
    for row in predictions:
        if ((row["true_label"] == "collie"
             and row["pred_label"] == "border_collie")
                or (row["true_label"] == "border_collie"
                    and row["pred_label"] == "collie")):
            push(5, "collie<->border_collie 互误", row,
                 "两者为不同品种，核对毛长/体型/头部；不得合并类别")

    # 去重（同一样本同一优先级只留一条）
    deduped: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in queue:
        key = (str(item["priority"]), item["sample_id"] or item["image_path"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    def sort_key(item: dict):
        try:
            probability = float(item["top1_prob"])
        except (TypeError, ValueError):
            probability = 0.0
        return (item["priority"], -probability)

    deduped.sort(key=sort_key)

    out_path = in_dir / OUT_NAME
    if out_path.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = in_dir / f"manual_review_queue_{stamp}.csv"
        print(f"[queue] 目标已存在，改写到 {out_path.name}")
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(deduped)

    counts: dict[int, int] = {}
    for item in deduped:
        counts[item["priority"]] = counts.get(item["priority"], 0) + 1
    print(f"[queue] 共 {len(deduped)} 条：")
    for priority in sorted(counts):
        print(f"  priority {priority}: {counts[priority]}")
    print(f"[queue] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
