#!/usr/bin/env python
"""U5.4 候选组同图一致性检查（只读数据，不训练）。

用法（在仓库根目录执行）::

    python scripts/check_candidate_consistency.py

用**同一张 validation 图片**在隔离环境（临时 SQLite + 临时 uploads）中：

1. 候选开关**开启**时连续请求 5 次 ``POST /api/predict``，检查
   ``candidate_group.triggered``、四候选成员与顺序、原始 Top-1 标签是否稳定，
   记录原始 Top-1 分数的最大绝对差，并逐次验证组内得分严格等于
   ``p_i / group_mass * 100`` 且和为 100；
2. 候选开关**关闭**时请求 1 次，检查响应不含候选组，且原始 Top-1 与开启态一致。

复用 ``scripts/run_four_breed_backend.build_isolated_app`` 作为隔离启动器
（自建 Settings + PredictorService，**不修改任何生产默认值**），
临时 DB/uploads 落在本报告目录的 ``runtime_on/`` 与 ``runtime_off/`` 下，
与正式 ``data/app.db``、项目 ``uploads/`` **物理隔离**。

**不读 test split**：只使用 ``data/v2_processed/val`` 中的一张图片。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from scripts.run_four_breed_backend import build_isolated_app  # noqa: E402

DEFAULT_OUT = _REPO_ROOT / "reports" / "v2_1_four_breed_consistency_review"
DEFAULT_IMAGE = (_REPO_ROOT / "data" / "v2_processed" / "val"
                 / "american_pit_bull_terrier"
                 / "american_pit_bull_terrier_132.jpg")

EXPECTED_GROUP = (
    "american_pit_bull_terrier",
    "american_staffordshire_terrier",
    "staffordshire_bull_terrier",
    "american_bulldog",
)
EXPECTED_THRESHOLD_VERSION = "val-2026-10-19-four-breed-b1"

CHECKS: list[dict] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    CHECKS.append({"check": name, "passed": bool(passed), "detail": detail})
    mark = "PASS" if passed else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))


def post_image(client: TestClient, image_path: Path, top_k: int = 3) -> dict:
    """上传**原始字节**（不重新编码），避免像素漂移影响一致性比较。"""
    data = image_path.read_bytes()
    response = client.post(
        "/api/predict",
        files={"file": (image_path.name, data, "image/jpeg")},
        data={"top_k": str(top_k)})
    assert response.status_code == 200, (
        f"HTTP {response.status_code} {response.text[:300]}")
    return response.json()


def flatten(payload: dict, index: int, switch_state: str) -> dict:
    """把一次响应压平成 CSV 行。"""
    predictions = payload.get("predictions") or []
    group = payload.get("candidate_group") or {}
    candidates = group.get("candidates") or []
    row = {
        "request_index": index,
        "switch_state": switch_state,
        "record_id": payload.get("record_id", ""),
        "top1_label": predictions[0]["breed"] if predictions else "",
        "top1_probability": (f"{predictions[0]['confidence']:.10f}"
                             if predictions else ""),
        "top2_label": predictions[1]["breed"] if len(predictions) > 1 else "",
        "top3_label": predictions[2]["breed"] if len(predictions) > 2 else "",
        "predictions_digest": json.dumps(predictions, ensure_ascii=False),
        "candidate_group_present": payload.get("candidate_group") is not None,
        "triggered": group.get("triggered", ""),
        "threshold_version": group.get("threshold_version", ""),
        "group_mass": group.get("group_mass", ""),
        "group_margin": group.get("group_margin", ""),
        "candidate_order": ";".join(item["breed"] for item in candidates),
        "group_score_sum": (
            round(sum(item["group_score"] for item in candidates), 6)
            if candidates else ""),
    }
    for slot in range(4):
        if slot < len(candidates):
            row[f"candidate_{slot + 1}_breed"] = candidates[slot]["breed"]
            row[f"candidate_{slot + 1}_original"] = candidates[slot][
                "original_confidence"]
            row[f"candidate_{slot + 1}_group_score"] = candidates[slot][
                "group_score"]
        else:
            row[f"candidate_{slot + 1}_breed"] = ""
            row[f"candidate_{slot + 1}_original"] = ""
            row[f"candidate_{slot + 1}_group_score"] = ""
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args(argv)

    if not args.image.exists():
        print(f"[consistency] missing image: {args.image}", file=sys.stderr)
        return 1
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    runs_on: list[dict] = []
    runs_off: list[dict] = []
    payloads_on: list[dict] = []
    payload_off: dict | None = None

    # ================= 1. 开关开启，连续 N 次 =================
    print()
    print(f"=== 1. 开关开启：同一张图连续 {args.repeats} 次 ===")
    with TestClient(build_isolated_app(out_dir / "runtime_on",
                                       enable_candidate_group=True)) as client:
        for index in range(1, args.repeats + 1):
            payload = post_image(client, args.image)
            payloads_on.append(payload)
            row = flatten(payload, index, "on")
            runs_on.append(row)
            group = payload.get("candidate_group") or {}
            print(f"  #{index} top1={row['top1_label']} "
                  f"p={row['top1_probability']} "
                  f"triggered={row['triggered']} "
                  f"sum={row['group_score_sum']}")

    # ================= 2. 开关关闭，1 次 =================
    print()
    print("=== 2. 开关关闭：同一张图 1 次 ===")
    with TestClient(build_isolated_app(out_dir / "runtime_off",
                                       enable_candidate_group=False)) as client:
        payload_off = post_image(client, args.image)
        row = flatten(payload_off, 1, "off")
        runs_off.append(row)
        print(f"  #1 top1={row['top1_label']} p={row['top1_probability']} "
              f"candidate_group_present={row['candidate_group_present']}")

    # ================= 3. 稳定性校验 =================
    print()
    print("=== 3. 同开关配置下的稳定性校验（UNEXPECTED_INCONSISTENCY）===")
    triggers = [row["triggered"] for row in runs_on]
    record("开启态 triggered 全部相同", len(set(map(str, triggers))) == 1,
           f"{triggers}")
    record("开启态 triggered 为 True", triggers[0] is True, f"{triggers[0]}")

    orders = [row["candidate_order"] for row in runs_on]
    record("四候选成员与顺序 5 次完全一致", len(set(orders)) == 1, orders[0])
    record("候选成员与四类 B1 定义一致（集合相同）",
           set(orders[0].split(";")) == set(EXPECTED_GROUP)
           if orders[0] else False, f"{orders[0]}")

    top1_labels = [row["top1_label"] for row in runs_on]
    record("原始 Top-1 标签 5 次完全一致", len(set(top1_labels)) == 1,
           top1_labels[0])

    probs = [float(row["top1_probability"]) for row in runs_on]
    max_abs_diff = max(probs) - min(probs)
    record("原始 Top-1 分数 5 次一致（batch=1 预期逐位相同）",
           max_abs_diff == 0.0,
           f"max_abs_diff={max_abs_diff:.3e} (min={min(probs):.10f}, "
           f"max={max(probs):.10f})")

    versions = {row["threshold_version"] for row in runs_on}
    record("threshold_version 恒为四类 B1",
           versions == {EXPECTED_THRESHOLD_VERSION}, f"{versions}")

    sums = [float(row["group_score_sum"]) for row in runs_on]
    record("组内得分之和每次均 ≈ 100%",
           all(abs(value - 100.0) <= 1e-3 for value in sums),
           f"sums={[round(v, 6) for v in sums]}")

    # 逐项：group_score == original / group_mass * 100
    normalised_ok = True
    worst = 0.0
    for payload in payloads_on:
        group = payload["candidate_group"]
        mass = group["group_mass"]
        for item in group["candidates"]:
            expected = item["original_confidence"] / mass * 100
            deviation = abs(item["group_score"] - expected)
            worst = max(worst, deviation)
            if deviation > 1e-3:
                normalised_ok = False
    record("组内得分严格等于原始概率归一化（容差 1e-3）", normalised_ok,
           f"max_deviation={worst:.3e}")

    # 候选原始概率 5 次一致
    original_digests = {
        json.dumps([(item["breed"], item["original_confidence"])
                    for item in payload["candidate_group"]["candidates"]],
                   ensure_ascii=False)
        for payload in payloads_on}
    record("四候选原始 Softmax 分数 5 次完全一致",
           len(original_digests) == 1, f"{len(original_digests)} 种取值")

    # Top-K 全数组 5 次一致
    topk_digests = {row["predictions_digest"] for row in runs_on}
    record("原始 Top-K 全数组 5 次完全一致", len(topk_digests) == 1,
           f"{len(topk_digests)} 种取值")

    # ================= 4. 开/关对照（EXPECTED_BY_DESIGN）=================
    print()
    print("=== 4. 开/关对照（EXPECTED_BY_DESIGN）===")
    off_row = runs_off[0]
    record("开启态返回候选组", runs_on[0]["candidate_group_present"] is True)
    record("关闭态不返回候选组",
           payload_off.get("candidate_group") is None,
           f"candidate_group={payload_off.get('candidate_group')}")
    record("关闭态 triggered 字段不存在（键缺失语义）",
           off_row["triggered"] == "", f"{off_row['triggered']}")
    record("开/关两态原始 Top-1 标签一致",
           off_row["top1_label"] == runs_on[0]["top1_label"],
           f"{off_row['top1_label']} vs {runs_on[0]['top1_label']}")
    off_prob = float(off_row["top1_probability"])
    record("开/关两态原始 Top-1 分数一致",
           abs(off_prob - probs[0]) == 0.0,
           f"off={off_prob:.10f} on={probs[0]:.10f}")
    record("开/关两态原始 Top-K 全数组一致",
           off_row["predictions_digest"] == runs_on[0]["predictions_digest"])

    # ================= 5. 输出 CSV =================
    fieldnames = [
        "request_index", "switch_state", "record_id",
        "top1_label", "top1_probability", "top2_label", "top3_label",
        "candidate_group_present", "triggered", "threshold_version",
        "group_mass", "group_margin", "candidate_order", "group_score_sum",
    ]
    for slot in range(4):
        fieldnames += [f"candidate_{slot + 1}_breed",
                       f"candidate_{slot + 1}_original",
                       f"candidate_{slot + 1}_group_score"]
    fieldnames.append("predictions_digest")

    csv_path = out_dir / "same_image_repeated_requests.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in runs_on + runs_off:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    print()
    print(f"[consistency] wrote {csv_path}")

    # ================= 6. 汇总 JSON =================
    passed = sum(1 for check in CHECKS if check["passed"])
    failed = [check for check in CHECKS if not check["passed"]]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "image": str(args.image),
        "split_used": "validation only (test split never read)",
        "test_split_access_count": 0,
        "repeats": args.repeats,
        "checks": CHECKS,
        "passed": passed,
        "total": len(CHECKS),
        "max_top1_abs_diff": max_abs_diff,
        "group_score_sum_min": min(sums),
        "group_score_sum_max": max(sums),
        "max_group_normalisation_deviation": worst,
        "unexpected_inconsistency": failed,
        "expected_by_design": [
            {"item": "开启态返回候选组并显示四候选",
             "observed": runs_on[0]["candidate_group_present"] is True},
            {"item": "关闭态不返回候选组（前端不显示候选区）",
             "observed": payload_off.get("candidate_group") is None},
            {"item": "开关不改变原始 Top-1 与 Top-K",
             "observed": (off_row["top1_label"] == runs_on[0]["top1_label"]
                          and off_row["predictions_digest"]
                          == runs_on[0]["predictions_digest"])},
        ],
    }
    json_path = out_dir / "consistency_summary.json"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    print(f"[consistency] wrote {json_path}")

    print()
    print(f"[consistency] {passed}/{len(CHECKS)} 项通过，失败 {len(failed)} 项")
    for item in failed:
        print(f"    FAIL: {item['check']} — {item['detail']}")
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
