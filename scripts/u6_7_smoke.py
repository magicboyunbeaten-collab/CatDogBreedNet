#!/usr/bin/env python
"""U6.7 阶段 C 验收：默认配置（exp06, 256）下的候选提示契约冒烟。

只重定向 DB / uploads；权重路径、类别映射、分辨率、候选开关全部走
``config.py`` 默认值，因此验证的是默认启动行为。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(".").resolve()
OUT = REPO / "reports" / "u6_7_exp06_collie_pair"
BASE = "http://127.0.0.1:8000"
VAL = REPO / "data" / "v2_processed" / "val"

SAMPLES = [
    {"role": "collie-pair-trigger",
     "rel": "border_collie/n02106166_416.jpg",
     "expect_triggered": True, "expect_group_id": "collie-pair"},
    {"role": "four-breed-trigger",
     "rel": "american_pit_bull_terrier/american_pit_bull_terrier_132.jpg",
     "expect_triggered": True, "expect_group_id": "four-breed-bully"},
    {"role": "non-target-control",
     "rel": "beagle/beagle_101.jpg",
     "expect_triggered": False, "expect_group_id": None},
    {"role": "collie-pair-non-trigger",
     "rel": "border_collie/n02106166_204.jpg",
     "expect_triggered": False, "expect_group_id": None},
]


def main() -> int:
    results = []
    all_ok = True
    for spec in SAMPLES:
        path = VAL / spec["rel"]
        payload = requests.post(
            f"{BASE}/api/predict",
            files={"file": (path.name, path.read_bytes(), "image/jpeg")},
            data={"top_k": "3"}, timeout=180).json()
        group = payload.get("candidate_group") or {}
        top1 = payload["predictions"][0]
        triggered = bool(group.get("triggered"))

        inv = {
            "http_ok": True,
            "topk_len_3": len(payload["predictions"]) == 3,
            "no_probabilities_field": "probabilities" not in payload,
            "top1_breed_preserved": (group.get("top1_breed") == top1["breed"]
                                     if group else True),
            "top1_confidence_preserved": (
                abs(group.get("top1_confidence", -1) - top1["confidence"]) < 1e-9
                if group else True),
            "triggered_as_expected": triggered == spec["expect_triggered"],
            "group_id_as_expected": (
                (group.get("group_id") if triggered else None)
                == spec["expect_group_id"]),
        }
        if triggered:
            total = sum(c["group_score"] for c in group["candidates"])
            inv["group_score_sum_100"] = abs(total - 100.0) <= 1e-3
            inv["scores_equal_normalisation"] = all(
                abs(c["group_score"]
                    - c["original_confidence"] / group["group_mass"] * 100)
                <= 1e-3 for c in group["candidates"])
            inv["v2_threshold_version"] = (
                group.get("threshold_version")
                == "val-2026-10-21-collie-pair-v2"
                if group.get("group_id") == "collie-pair" else None)
            inv["group_share_present"] = (
                group.get("group_share") is not None
                if group.get("group_id") == "collie-pair" else None)
            score_sum = round(total, 6)
        else:
            for k in ("group_score_sum_100", "scores_equal_normalisation",
                      "v2_threshold_version", "group_share_present"):
                inv[k] = None
            score_sum = None

        passed = all(v is True or v is None for v in inv.values())
        all_ok = all_ok and passed
        results.append({
            "role": spec["role"],
            "image": str(path.relative_to(REPO)).replace("\\", "/"),
            "original_predictions": payload["predictions"],
            "triggered": triggered,
            "candidate_group_id": group.get("group_id"),
            "threshold_version": group.get("threshold_version"),
            "group_mass": group.get("group_mass"),
            "group_margin": group.get("group_margin"),
            "group_share": group.get("group_share"),
            "trigger_reason": group.get("reason"),
            "candidates": group.get("candidates", []),
            "group_score_sum": score_sum,
            "invariants": inv,
            "passed": passed,
        })
        print(f"\n[{spec['role']}] {spec['rel']}")
        print(f"  Top-1={top1['breed']} ({top1['confidence']:.6f})  "
              f"triggered={triggered}  group_id={group.get('group_id')}")
        if triggered:
            print(f"  version={group.get('threshold_version')} "
                  f"mass={group.get('group_mass')} "
                  f"margin={group.get('group_margin')} "
                  f"share={group.get('group_share')} sum={score_sum}")
            for c in group["candidates"]:
                print(f"    {c['breed_zh']:<10} orig={c['original_confidence']:.6f} "
                      f"score={c['group_score']:.4f}")
        for k, v in inv.items():
            mark = "PASS" if v is True else ("n/a" if v is None else "FAIL")
            print(f"    [{mark}] {k}")

    health = requests.get(f"{BASE}/api/health", timeout=15).json()
    log_lines = Path(".cache/u67_web.err").read_text(
        encoding="utf-8", errors="replace").splitlines()
    identity = [l for l in log_lines
                if "model ready" in l or "class mapping verified" in l]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "isolated_runtime": "reports/u6_7_exp06_collie_pair/runtime",
        "env_overrides_applied": {
            "CATDOG_DB_PATH": "reports/u6_7_exp06_collie_pair/runtime/app.db",
            "CATDOG_UPLOAD_DIR": "reports/u6_7_exp06_collie_pair/runtime/uploads",
            "CATDOG_WEIGHTS_PATH": None,
            "CATDOG_CLASS_NAMES_PATH": None,
            "CATDOG_IMAGE_SIZE": None,
            "CATDOG_CANDIDATE_GROUP_ENABLED": None,
        },
        "note": "只重定向数据库与上传目录；权重/映射/分辨率/候选开关均为默认值。",
        "health": health,
        "startup_log_identity_lines": identity,
        "samples": results,
        "all_passed": all_ok,
    }
    (OUT / "runtime_smoke.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 62)
    print(f"health: num_classes={health['num_classes']} "
          f"model_version={health.get('model_version')} "
          f"model_error={health.get('model_error')}")
    print(f"ALL_PASSED = {all_ok}")
    return 0 if all_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
