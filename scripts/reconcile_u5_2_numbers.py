#!/usr/bin/env python
"""U5.3 报告口径核对：复算 U5.2 验收报告中的四个基础数字（只读）。

用法（在仓库根目录执行）::

    python scripts/reconcile_u5_2_numbers.py

从三份 U5.1 代表性清单、U5.2 的 ``validation_samples_four_breed.csv`` 与
``acceptance_api_responses.json`` 复算：

* 来源**记录**数；
* **唯一图片**数；
* 四类**实际触发**的唯一图片数；
* API 验收**检查项**数；
* 未触发对照数。

只读三个既有报告目录，不写入、不覆盖。结果写入 U5.3 新目录的
``reconcile_stats.json``。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

U51_DIR = _REPO_ROOT / "reports" / "v2_1_apbt_four_breed_candidate_eval"
U52_DIR = _REPO_ROOT / "reports" / "v2_1_four_breed_candidate_implementation"
DEFAULT_OUT = _REPO_ROOT / "reports" / "v2_1_four_breed_page_acceptance"

SOURCES = (
    ("newly_triggered_by_apbt.csv", "newly_triggered_by_apbt"),
    ("triggered_by_both_strategies.csv", "triggered_by_both"),
    ("out_of_group_trigger_examples.csv", "out_of_group"),
)


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"missing {path}")
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1. 三份 U5.1 清单 ----
    per_source: dict[str, int] = {}
    all_paths: list[str] = []
    per_source_paths: dict[str, set[str]] = {}
    for filename, key in SOURCES:
        rows = read_csv(U51_DIR / filename)
        paths = [row["image_path"] for row in rows]
        per_source[key] = len(rows)
        per_source_paths[key] = set(paths)
        all_paths.extend(paths)

    record_count = len(all_paths)
    unique_paths = set(all_paths)
    duplicates = {path: count for path, count in Counter(all_paths).items()
                  if count > 1}

    # ---- 2. 代表样本 CSV ----
    samples = read_csv(U52_DIR / "validation_samples_four_breed.csv")
    sample_sources = Counter(row["source"] for row in samples)
    sample_ids = [row["sample_id"] for row in samples]
    triggered_flags = Counter(str(row["triggered_4"]).lower()
                              for row in samples)

    # ---- 3. 验收 JSON ----
    payload = json.loads(
        (U52_DIR / "acceptance_api_responses.json").read_text(encoding="utf-8"))
    evidence = payload["evidence"]
    triggered_evidence = evidence["triggered"]
    controls = evidence["controls"]
    switch_off = evidence["switch_off"]

    triggered_unique = {item["image"] for item in triggered_evidence}
    triggered_true = [
        item for item in triggered_evidence
        if (item["response"].get("candidate_group") or {}).get("triggered")]

    # ---- 4. 关系推导 ----
    both_keys = per_source_paths["newly_triggered_by_apbt"] \
        | per_source_paths["triggered_by_both"]
    out_of_group_only = (per_source_paths["out_of_group"] - both_keys)
    overlap_newly_both = (per_source_paths["newly_triggered_by_apbt"]
                          & per_source_paths["triggered_by_both"])

    stats = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources_read": [str(U51_DIR / f) for f, _ in SOURCES]
                        + [str(U52_DIR / "validation_samples_four_breed.csv"),
                           str(U52_DIR / "acceptance_api_responses.json")],
        "per_source_record_counts": per_source,
        "source_record_total": record_count,
        "unique_image_count_across_sources": len(unique_paths),
        "duplicate_records": duplicates,
        "sample_csv": {
            "rows": len(samples),
            "unique_sample_ids": len(set(sample_ids)),
            "by_source": dict(sample_sources),
            "triggered_flag_counts": dict(triggered_flags),
        },
        "acceptance_json": {
            "check_items": len(payload["checks"]),
            "passed": payload["passed"],
            "evidence_triggered_records": len(triggered_evidence),
            "evidence_triggered_unique_images": len(triggered_unique),
            "evidence_triggered_true": len(triggered_true),
            "controls": len(controls),
            "switch_off": len(switch_off),
        },
        "relations": {
            "nineteen_is": ("source records 16 + controls 3 = 19 条记录；"
                            f"对应唯一图片 {len(unique_paths) + len(controls)} 张"),
            "sixteen_is": "7 (newly) + 5 (both) + 4 (out_of_group) = 16 条记录",
            "twelve_is": ("7 (newly) + 5 (both) = 12 张唯一触发图；"
                          "out_of_group 的 4 张全部已包含在这 12 张内"),
            "newly_vs_both_overlap": len(overlap_newly_both),
            "out_of_group_only_new_images": len(out_of_group_only),
            "out_of_group_is_subset_of_12": len(out_of_group_only) == 0,
        },
    }

    out_path = out_dir / "reconcile_stats.json"
    out_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False),
                        encoding="utf-8")

    print(f"[reconcile] 三份 U5.1 清单记录: {per_source} = {record_count}")
    print(f"[reconcile] 唯一图片: {len(unique_paths)}；重复记录: "
          f"{len(duplicates)} 张")
    print(f"[reconcile] 样本 CSV: {len(samples)} 行 / "
          f"{len(set(sample_ids))} 唯一 sample_id")
    print(f"[reconcile] 验收用例: {len(payload['checks'])} 项"
          f"（passed {payload['passed']}）")
    print(f"[reconcile] evidence.triggered: {len(triggered_evidence)} 条 / "
          f"{len(triggered_unique)} 唯一；controls {len(controls)}；"
          f"switch_off {len(switch_off)}")
    print(f"[reconcile] newly∩both = {len(overlap_newly_both)}（应为 0）")
    print(f"[reconcile] out_of_group 独有图片 = {len(out_of_group_only)}"
          f"（0 表示它是那 12 张的子集）")
    print(f"[reconcile] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
