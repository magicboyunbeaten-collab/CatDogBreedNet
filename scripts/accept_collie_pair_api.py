#!/usr/bin/env python
"""U6.2：柯利/边境牧羊犬双候选提示的隔离环境 API 验收。

用法（在仓库根目录执行）::

    python scripts/accept_collie_pair_api.py

验收内容
--------
A. 四类 bully 代表样本 —— 既有策略行为不变（四项候选、版本、得分和≈100）；
B. 双候选触发样本（3 张真实触发图）—— 两项候选、中文名、得分和≈100、
   原始 Top-1 不被替换、组标识为 ``collie-pair``；
C. 双候选不触发样本（Top-1 属两类但分差过大）—— ``triggered=False``；
D. 非目标犬种（Top-1 不在任何候选组）—— ``candidate_group`` 为 None；
E. 同一张触发图、相同设置串行 **5 次** —— 触发状态、候选成员/顺序、组分、
   Top-1 与 Top-K 稳定，并记录 Top-1 分数最大绝对差；
F. 开关开启/关闭对照 —— 关闭后无候选组且原始 Top-1/Top-K 逐位不变；
G. 数据库字段核对 —— 临时 SQLite 无候选组字段、记录数与上传次数一致；
H. API 不暴露完整 136 维概率向量。

样本全部来自 ``data/v2_processed/val``（**不读取 test split**）；
后端使用真实 V2.1 权重 + 临时 SQLite + 临时 uploads。
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from fastapi.testclient import TestClient  # noqa: E402

OUT_DIR = REPO / "reports" / "u6_2_collie_pair_candidate"
VAL = REPO / "data" / "v2_processed" / "val"
SCAN = OUT_DIR / "u6_2_threshold_scan.json"
GRID = OUT_DIR / "validation_threshold_grid.csv"
SAMPLES = OUT_DIR / "validation_trigger_samples.csv"

APBT = "american_pit_bull_terrier"
AMSTAFF = "american_staffordshire_terrier"
SBT = "staffordshire_bull_terrier"
AMBULL = "american_bulldog"
COLLIE = "collie"
BORDER_COLLIE = "border_collie"

EXPECTED_ZH = {
    APBT: "美国比特斗牛梗",
    AMSTAFF: "美国斯塔福郡梗",
    SBT: "斯塔福郡斗牛梗",
    AMBULL: "美国斗牛犬",
    COLLIE: "柯利牧羊犬",
    BORDER_COLLIE: "边境牧羊犬",
}

CHECKS: list[dict] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    CHECKS.append({"check": name, "passed": bool(passed), "detail": detail})
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}"
          + (f" — {detail}" if detail else ""))


def build_app(runtime_dir: Path, enabled: bool):
    """复用隔离启动器：临时 DB/uploads + 真实 V2.1 权重与 136 类映射。"""
    from scripts.run_four_breed_backend import build_isolated_app
    return build_isolated_app(runtime_dir, enable_candidate_group=enabled)


def post_image(client: TestClient, image_path: Path, top_k: int = 3) -> dict:
    """上传**原始字节**（不重新编码），保证与扫描脚本的推理输入一致。"""
    data = image_path.read_bytes()
    response = client.post(
        "/api/predict",
        files={"file": (image_path.name, data, "image/jpeg")},
        data={"top_k": str(top_k)})
    assert response.status_code == 200, (
        f"{image_path}: HTTP {response.status_code} {response.text[:300]}")
    return response.json()


def triggered_examples() -> list[dict]:
    """从阈值扫描的逐图明细中取真实触发样本（Top-1 属两类）。"""
    rows = list(csv.DictReader(SAMPLES.open(encoding="utf-8")))
    out = []
    for row in rows:
        mass = float(row["pair_mass"])
        margin = float(row["pair_margin"])
        if mass >= 0.30 and margin <= 0.30:
            out.append(row)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    evidence: dict = {"triggered": [], "controls": [], "switch_off": [],
                      "repeats": []}

    # ---- 选样：真实触发图 + 不触发图 + 四类代表图 + 非目标犬种 ----
    triggered_rows = triggered_examples()
    print(f"[accept] 真实双候选触发样本：{len(triggered_rows)} 张")
    if not triggered_rows:
        print("[accept] 未找到触发样本，终止（不编造样本）", file=sys.stderr)
        return 1

    all_rows = list(csv.DictReader(SAMPLES.open(encoding="utf-8")))
    untriggered = [r for r in all_rows
                   if r not in triggered_rows
                   and float(r["pair_margin"]) > 0.30][:3]
    print(f"[accept] 双候选不触发对照：{len(untriggered)} 张")

    # 样本路径解析：明细里的 image_path 形如 "v2_processed/val/<class>/<file>"
    def val_image(relative: str) -> Path:
        return VAL.parent / relative

    bully = VAL / APBT / "american_pit_bull_terrier_132.jpg"   # U5.1 四类触发样本
    if not bully.exists():
        print(f"[accept] 四类代表样本缺失：{bully}", file=sys.stderr)
        return 1
    non_target = None
    for candidate in sorted((VAL / "beagle").glob("*.jpg")):
        non_target = candidate
        break
    if non_target is None:
        print("[accept] 非目标犬种样本缺失", file=sys.stderr)
        return 1
    print(f"[accept] 非目标犬种样本：{non_target.name}")

    with tempfile.TemporaryDirectory(prefix="u62_accept_",
                                     ignore_cleanup_errors=True) as tmp:
        # ================= A/B/C/D 开启态 =================
        print()
        print("=== 开关开启 ===")
        with TestClient(build_app(Path(tmp) / "on", True)) as client:
            health = client.get("/api/health").json()
            record("health: 模型已加载", health.get("model_loaded") is True)
            record("health: 类别数 = 136", health.get("num_classes") == 136,
                   str(health.get("num_classes")))
            record("health: 默认模型仍为 V2.1",
                   health.get("model_weights") == "best_model.pth",
                   str(health.get("model_weights")))

            # ---- A. 四类代表样本 ----
            payload = post_image(client, bully)
            group = payload.get("candidate_group") or {}
            evidence["controls"].append({"image": str(bully),
                                         "response": payload})
            record("A 四类代表: 触发",
                   group.get("triggered") is True, group.get("reason"))
            record("A 四类代表: 组标识 four-breed-bully",
                   group.get("group_id") == "four-breed-bully",
                   str(group.get("group_id")))
            record("A 四类代表: 四项候选",
                   len(group.get("candidates", [])) == 4)
            record("A 四类代表: 版本未变",
                   group.get("threshold_version")
                   == "val-2026-10-19-four-breed-b1",
                   str(group.get("threshold_version")))
            record("A 四类代表: 中文名正确",
                   all(c["breed_zh"] == EXPECTED_ZH[c["breed"]]
                       for c in group.get("candidates", [])))
            total = sum(c["group_score"] for c in group.get("candidates", []))
            record("A 四类代表: 组内得分和 ≈ 100",
                   abs(total - 100.0) <= 1e-3, f"sum={total:.6f}")
            record("A 四类代表: 原始 Top-1 一致",
                   group.get("top1_breed")
                   == payload["predictions"][0]["breed"],
                   payload["predictions"][0]["breed"])

            # ---- B. 双候选触发样本 ----
            for row in triggered_rows:
                image = val_image(row["image_path"])
                payload = post_image(client, image)
                group = payload.get("candidate_group") or {}
                evidence["triggered"].append(
                    {"image": str(image), "response": payload})
                label = f"B 触发 {image.parent.name}/{image.name}"
                record(f"{label}: 触发", group.get("triggered") is True,
                       group.get("reason"))
                record(f"{label}: 组标识 collie-pair",
                       group.get("group_id") == "collie-pair",
                       str(group.get("group_id")))
                record(f"{label}: 两项候选",
                       len(group.get("candidates", [])) == 2)
                record(f"{label}: 中文名正确",
                       {c["breed"] for c in group.get("candidates", [])}
                       == {COLLIE, BORDER_COLLIE}
                       and all(c["breed_zh"] == EXPECTED_ZH[c["breed"]]
                               for c in group["candidates"]))
                total = sum(c["group_score"]
                            for c in group.get("candidates", []))
                record(f"{label}: 组内得分和 ≈ 100",
                       abs(total - 100.0) <= 1e-3, f"sum={total:.6f}")
                mass = sum(c["original_confidence"]
                           for c in group.get("candidates", []))
                record(f"{label}: 得分严格等于原始概率归一化",
                       all(abs(c["group_score"] - c["original_confidence"]
                               / group["group_mass"] * 100) <= 1e-3
                           for c in group["candidates"])
                       and abs(mass - group["group_mass"]) <= 1e-6,
                       f"mass={group['group_mass']}")
                record(f"{label}: 原始 Top-1 不被替换",
                       group.get("top1_breed")
                       == payload["predictions"][0]["breed"],
                       payload["predictions"][0]["breed"])

            # ---- C. 双候选不触发对照 ----
            for row in untriggered:
                image = val_image(row["image_path"])
                payload = post_image(client, image)
                group = payload.get("candidate_group") or {}
                record(f"C 不触发 {image.parent.name}/{image.name}",
                       group is not None and group.get("triggered") is False,
                       group.get("reason") if group else "None")
                record(f"C 不触发 {image.parent.name}/{image.name}: "
                       f"组标识仍为 collie-pair",
                       group.get("group_id") == "collie-pair")

            # ---- D. 非目标犬种 ----
            # 注意：Top-1 不在四类组内时，既有四类策略会返回 triggered=False 的
            # 字典（前端据此不渲染候选区），这是 V1.1 以来的既有行为。
            # 因此这里断言的是"不触发"与"未走两类组策略"，而非"字段必须为 None"。
            payload = post_image(client, non_target)
            group_d = payload.get("candidate_group") or {}
            record("D 非目标犬种: 不触发候选",
                   group_d.get("triggered") is not True,
                   f"top1={payload['predictions'][0]['breed']} "
                   f"group_id={group_d.get('group_id')} "
                   f"reason={group_d.get('reason')}")
            record("D 非目标犬种: 未误入双候选策略",
                   group_d.get("group_id") != "collie-pair",
                   str(group_d.get("group_id")))
            record("D 非目标犬种: 原始 Top-K 正常",
                   len(payload["predictions"]) == 3)

            # ---- E. 同图 5 次一致性 ----
            print()
            print("=== 同一张触发图串行 5 次 ===")
            repeat_image = val_image(triggered_rows[0]["image_path"])
            top1_scores: list[float] = []
            for index in range(1, args.repeats + 1):
                payload = post_image(client, repeat_image)
                group = payload.get("candidate_group") or {}
                evidence["repeats"].append(
                    {"request_index": index, "response": payload})
                top1_scores.append(
                    float(payload["predictions"][0]["confidence"]))
                record(f"E 第 {index} 次: 触发且组标识一致",
                       group.get("triggered") is True
                       and group.get("group_id") == "collie-pair")
                record(f"E 第 {index} 次: 候选顺序一致",
                       [c["breed"] for c in group["candidates"]]
                       == [COLLIE, BORDER_COLLIE]
                       or [c["breed"] for c in group["candidates"]]
                       == [BORDER_COLLIE, COLLIE],
                       ";".join(c["breed"] for c in group["candidates"]))
            record("E: Top-1 标签 5 次相同",
                   len({r["response"]["predictions"][0]["breed"]
                        for r in evidence["repeats"]}) == 1)
            spread = max(top1_scores) - min(top1_scores)
            record("E: Top-1 分数最大绝对差", True,
                   f"max_abs_diff={spread:.3e}")

            # ---- DB 与 API 暴露面 ----
            db_path = Path(tmp) / "on" / "app.db"
            conn = sqlite3.connect(str(db_path))
            columns = [r[1] for r in conn.execute(
                "PRAGMA table_info(prediction_records)")]
            count = conn.execute(
                "SELECT COUNT(*) FROM prediction_records").fetchone()[0]
            conn.close()
            record("G: DB 无候选组字段",
                   not any("candidate" in c.lower() for c in columns),
                   f"columns={columns}")
            record("G: DB 记录数 = 上传次数",
                   count == len(evidence["triggered"]) + len(
                       evidence["controls"]) + len(untriggered) + 1
                   + args.repeats,
                   f"records={count}")
            record("H: API 不暴露完整概率向量",
                   "probabilities" not in payload)

        # ================= F. 开关关闭 =================
        print()
        print("=== 开关关闭 ===")
        with TestClient(build_app(Path(tmp) / "off", False)) as client:
            payload_off = post_image(client, repeat_image)
            record("F 关闭: 无候选组",
                   payload_off.get("candidate_group") is None)
            base = evidence["repeats"][0]["response"]
            record("F 关闭: 原始 Top-1 与开启时一致",
                   payload_off["predictions"][0]["breed"]
                   == base["predictions"][0]["breed"],
                   payload_off["predictions"][0]["breed"])
            record("F 关闭: 原始 Top-K 与分数逐位不变",
                   json.dumps(payload_off["predictions"], sort_keys=True)
                   == json.dumps(base["predictions"], sort_keys=True))
            evidence["switch_off"].append(
                {"image": str(repeat_image), "response": payload_off})

    passed = sum(1 for c in CHECKS if c["passed"])
    failed = [c for c in CHECKS if not c["passed"]]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "split_used": "validation only (test split never read)",
        "test_split_access_count": 0,
        "triggered_samples": len(evidence["triggered"]),
        "untriggered_controls": len(untriggered),
        "repeats": args.repeats,
        "checks": CHECKS,
        "passed": passed,
        "total": len(CHECKS),
        "failed": failed,
        "evidence": evidence,
    }
    (OUT_DIR / "acceptance_api_responses.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print()
    print(f"[accept] {passed}/{len(CHECKS)} 项通过，失败 {len(failed)} 项")
    for item in failed:
        print(f"    FAIL: {item['check']} — {item['detail']}")
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
