#!/usr/bin/env python
"""U5.5：V2.1 接入的隔离环境 API 验收（六场景 + 同图 5 次一致性）。

用法（在仓库根目录执行）::

    # 阶段 1：默认配置尚未切换，用显式 V2.1 注入跑通
    python scripts/accept_v2_1_integration.py --mode isolated

    # 阶段 2：默认配置已切换到 V2.1 后，验证"默认配置本身"能加载 136 类
    python scripts/accept_v2_1_integration.py --mode default

两种模式都使用**临时 SQLite + 临时 uploads**（不触碰正式 ``data/app.db``
与项目 ``uploads/``），样本全部来自 ``data/v2_processed/val``。

覆盖场景
--------
A. APBT/AmStaff 竞争样本 —— 四类候选按 B1 触发；
B. APBT 为 Top-1 的触发样本 —— 候选组含 APBT，原始 Top-1 不被替换；
C. SBT 触发样本 —— 触发；American Bulldog 用纯函数级验证（val 中无该
   Top-1 的触发样本，如实记录）；
D. 非候选组猫图 —— 不出现候选区；
E. 候选开关关闭 —— 不返回候选组，且原始 Top-1/Top-K/分数与开启态一致；
F. 同一图片同一配置连续 5 次 —— 触发状态、四候选顺序与得分稳定。
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

DEFAULT_OUT = _REPO_ROOT / "reports" / "u5_5_v2_1_integration"
VAL = _REPO_ROOT / "data" / "v2_processed" / "val"

APBT = "american_pit_bull_terrier"
AMSTAFF = "american_staffordshire_terrier"
SBT = "staffordshire_bull_terrier"
AMBULL = "american_bulldog"
EXPECTED_GROUP = (APBT, AMSTAFF, SBT, AMBULL)

SAMPLES = {
    # A: 真实 APBT，Top-1 被判为 AmStaff，组内 margin 仅 0.07 → 强竞争
    "competition": VAL / APBT / "american_pit_bull_terrier_11.jpg",
    # B: Top-1 就是 APBT（margin 0.076）
    "apbt_top1": VAL / APBT / "american_pit_bull_terrier_132.jpg",
    # C: Top-1 为 SBT 的唯一 val 触发样本
    "sbt_top1": VAL / SBT / "staffordshire_bull_terrier_160.jpg",
    # D: 非候选组（猫）
    "cat": VAL / "Abyssinian" / "Abyssinian_10.jpg",
}

CHECKS: list[dict] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    CHECKS.append({"check": name, "passed": bool(passed), "detail": detail})
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}"
          + (f" — {detail}" if detail else ""))


def build_app(runtime_dir: Path, enable_candidate_group: bool, mode: str):
    """构造隔离 app。

    ``mode='isolated'``：显式注入 V2.1 权重与 136 类映射（默认值尚未切换时用）。
    ``mode='default'`` ：用 ``Settings.from_env()`` 的**真实默认值**，只把
    db_path/upload_dir 换成临时目录 —— 用于证明"默认配置自身"能加载 136 类。
    """
    from backend.app.config import Settings
    from backend.app.main import create_app
    from backend.app.services.predictor import PredictorService

    runtime_dir.mkdir(parents=True, exist_ok=True)

    if mode == "isolated":
        v21 = _REPO_ROOT / "artifacts" / "v2_1_136classes_seed42"
        weights, class_names = v21 / "best_model.pth", v21 / "class_names.json"
    else:
        base = Settings.from_env()
        weights, class_names = base.weights_path, base.class_names_path

    settings = Settings(
        weights_path=weights,
        class_names_path=class_names,
        device="auto",
        upload_dir=runtime_dir / "uploads",
        db_path=runtime_dir / "app.db",
        cors_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        max_upload_bytes=10 * 1024 * 1024,
        max_image_pixels=25_000_000,
        candidate_group_enabled=enable_candidate_group,
    )
    service = PredictorService(
        weights_path=settings.weights_path, device=settings.device,
        class_names_path=settings.class_names_path,
        candidate_group_enabled=enable_candidate_group)
    print(f"[accept] mode={mode} weights={weights.name} "
          f"dir={weights.parent.name} classes={service.num_classes} "
          f"candidate_group={enable_candidate_group}")
    return create_app(settings=settings, predictor=service)


def post_image(client: TestClient, image_path: Path, top_k: int = 3) -> dict:
    data = image_path.read_bytes()
    response = client.post(
        "/api/predict",
        files={"file": (image_path.name, data, "image/jpeg")},
        data={"top_k": str(top_k)})
    assert response.status_code == 200, (
        f"{image_path.name}: HTTP {response.status_code} {response.text[:300]}")
    return response.json()


def triggered_ok(payload: dict, label: str) -> dict:
    """核对一次触发响应并返回 candidate_group。"""
    group = payload.get("candidate_group") or {}
    record(f"{label}: 候选组触发", group.get("triggered") is True,
           f"reason={group.get('reason')}")
    record(f"{label}: 四候选齐全",
           [c["breed"] for c in group.get("candidates", [])]
           and set(c["breed"] for c in group["candidates"]) == set(EXPECTED_GROUP),
           ";".join(c["breed"] for c in group.get("candidates", [])))
    record(f"{label}: 候选中文名齐全",
           all(c.get("breed_zh") for c in group.get("candidates", [])))
    total = sum(c["group_score"] for c in group.get("candidates", []))
    record(f"{label}: 组内得分和 ≈ 100", abs(total - 100.0) <= 1e-6,
           f"sum={total:.6f}")
    normalised = all(
        abs(c["group_score"] - c["original_confidence"]
            / group["group_mass"] * 100) <= 1e-3
        for c in group.get("candidates", []))
    record(f"{label}: 组内得分等于原始概率归一化", normalised)
    record(f"{label}: 原始 Top-1 与 predictions[0] 一致",
           group.get("top1_breed") == payload["predictions"][0]["breed"],
           payload["predictions"][0]["breed"])
    record(f"{label}: threshold_version 为四类 B1",
           group.get("threshold_version") == "val-2026-10-19-four-breed-b1",
           str(group.get("threshold_version")))
    return group


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=["isolated", "default"],
                        default="isolated")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args(argv)

    for key, path in SAMPLES.items():
        if not path.exists():
            print(f"[accept] missing sample {key}: {path}", file=sys.stderr)
            return 1

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = args.mode
    repeated_rows: list[dict] = []
    payloads_on: dict[str, dict] = {}

    # ================= 开关开启 =================
    print()
    print(f"=== 开关开启（mode={tag}）===")
    with TestClient(build_app(out_dir / f"runtime_{tag}_on",
                              enable_candidate_group=True,
                              mode=args.mode)) as client:
        health = client.get("/api/health").json()
        record("health: 模型已加载", health.get("model_loaded") is True)
        record("health: 类别数 = 136", health.get("num_classes") == 136,
               str(health.get("num_classes")))
        record("health: 回报实际加载的权重文件名",
               health.get("model_weights") == "best_model.pth",
               str(health.get("model_weights")))

        # --- A. APBT / AmStaff 竞争 ---
        payloads_on["competition"] = post_image(client, SAMPLES["competition"])
        group_a = triggered_ok(payloads_on["competition"], "A 竞争样本")
        names_a = [c["breed"] for c in group_a["candidates"]]
        record("A: 候选同时含 APBT 与 AmStaff",
               APBT in names_a and AMSTAFF in names_a)
        record("A: 原始 Top-1 为 AmStaff（未因候选逻辑改变）",
               payloads_on["competition"]["predictions"][0]["breed"] == AMSTAFF,
               payloads_on["competition"]["predictions"][0]["breed"])

        # --- B. APBT 为 Top-1 ---
        payloads_on["apbt_top1"] = post_image(client, SAMPLES["apbt_top1"])
        group_b = triggered_ok(payloads_on["apbt_top1"], "B APBT-Top1")
        record("B: 原始 Top-1 为 APBT",
               payloads_on["apbt_top1"]["predictions"][0]["breed"] == APBT,
               payloads_on["apbt_top1"]["predictions"][0]["breed"])
        record("B: 候选组含 APBT",
               APBT in [c["breed"] for c in group_b["candidates"]])

        # --- C. SBT ---
        payloads_on["sbt_top1"] = post_image(client, SAMPLES["sbt_top1"])
        triggered_ok(payloads_on["sbt_top1"], "C SBT-Top1")
        record("C: 原始 Top-1 为 SBT",
               payloads_on["sbt_top1"]["predictions"][0]["breed"] == SBT,
               payloads_on["sbt_top1"]["predictions"][0]["breed"])

        # --- D. 非候选组猫 ---
        # 注意：对组外图片，API 仍返回 candidate_group 对象但 triggered=False
        # （前端只在 triggered===true 时渲染候选区）。因此这里断言的是
        # "不触发"，而不是"字段缺失"。
        payloads_on["cat"] = post_image(client, SAMPLES["cat"])
        cat_group = payloads_on["cat"].get("candidate_group") or {}
        record("D: 非候选组猫图不触发候选组",
               cat_group.get("triggered") is not True,
               f"top1={payloads_on['cat']['predictions'][0]['breed']} "
               f"triggered={cat_group.get('triggered')} "
               f"reason={cat_group.get('reason')}")
        record("D: 猫图原始 Top-1 为 Abyssinian（猫）",
               payloads_on["cat"]["predictions"][0]["breed"] == "Abyssinian",
               payloads_on["cat"]["predictions"][0]["breed"])

        # --- F. 同图 5 次一致性 ---
        for index in range(1, args.repeats + 1):
            payload = post_image(client, SAMPLES["apbt_top1"])
            group = payload["candidate_group"]
            repeated_rows.append({
                "request_index": index,
                "switch_state": "on",
                "top1_label": payload["predictions"][0]["breed"],
                "top1_probability": f"{payload['predictions'][0]['confidence']:.10f}",
                "triggered": group["triggered"],
                "candidate_order": ";".join(c["breed"] for c in group["candidates"]),
                "group_mass": group["group_mass"],
                "group_margin": group["group_margin"],
                "group_score_sum": round(
                    sum(c["group_score"] for c in group["candidates"]), 6),
                "candidate_scores": ";".join(
                    f"{c['breed']}:{c['group_score']}"
                    for c in group["candidates"]),
            })

    # ================= 开关关闭 =================
    print()
    print("=== 开关关闭 ===")
    with TestClient(build_app(out_dir / f"runtime_{tag}_off",
                              enable_candidate_group=False,
                              mode=args.mode)) as client:
        payload_off = post_image(client, SAMPLES["apbt_top1"])
        repeated_rows.append({
            "request_index": 1,
            "switch_state": "off",
            "top1_label": payload_off["predictions"][0]["breed"],
            "top1_probability":
                f"{payload_off['predictions'][0]['confidence']:.10f}",
            "triggered": "",
            "candidate_order": "",
            "group_mass": "",
            "group_margin": "",
            "group_score_sum": "",
            "candidate_scores": "",
        })
    record("E: 关闭候选后不返回候选组",
           payload_off.get("candidate_group") is None)
    base = payloads_on["apbt_top1"]
    record("E: 关闭候选后原始 Top-1 不变",
           payload_off["predictions"][0]["breed"] == base["predictions"][0]["breed"],
           payload_off["predictions"][0]["breed"])
    record("E: 关闭候选后原始 Top-K 与分数逐位不变",
           json.dumps(payload_off["predictions"], sort_keys=True)
           == json.dumps(base["predictions"], sort_keys=True))

    # ================= F 校验 =================
    print()
    print("=== F. 同图 5 次一致性 ===")
    on_rows = [r for r in repeated_rows if r["switch_state"] == "on"]
    record("F: triggered 全部相同",
           len({str(r["triggered"]) for r in on_rows}) == 1,
           str([r["triggered"] for r in on_rows]))
    record("F: 四候选顺序全部相同",
           len({r["candidate_order"] for r in on_rows}) == 1,
           on_rows[0]["candidate_order"])
    record("F: 原始 Top-1 标签全部相同",
           len({r["top1_label"] for r in on_rows}) == 1,
           on_rows[0]["top1_label"])
    probs = [float(r["top1_probability"]) for r in on_rows]
    record("F: 原始 Top-1 分数最大绝对差记录", True,
           f"max_abs_diff={max(probs) - min(probs):.3e}")
    record("F: 组内得分和每次 ≈ 100",
           all(abs(float(r["group_score_sum"]) - 100.0) <= 1e-6 for r in on_rows),
           str([r["group_score_sum"] for r in on_rows]))

    # ================= 函数级补测：American Bulldog 触发 =================
    print()
    print("=== 函数级补测（American Bulldog 在 val 中无触发样本）===")
    from backend.app.services.candidate_group import build_candidate_group
    synthetic = [{"breed": AMBULL, "confidence": 0.45},
                 {"breed": AMSTAFF, "confidence": 0.30},
                 {"breed": APBT, "confidence": 0.15},
                 {"breed": "beagle", "confidence": 0.05}]
    group_syn = build_candidate_group(synthetic)
    record("AmBull-Top1 合成样本满足阈值时触发",
           group_syn["triggered"] is True, group_syn["reason"])
    record("AmBull-Top1 合成样本保留原始 Top-1",
           group_syn["top1_breed"] == AMBULL
           and group_syn["top1_confidence"] == 0.45)
    record("AmBull-Top1 合成样本组内得分和 = 100",
           abs(sum(c["group_score"] for c in group_syn["candidates"]) - 100) <= 1e-6)

    # ---- val 中 American Bulldog 作 Top-1 的真实统计（如实记录）----
    val_csv = (_REPO_ROOT / "reports" / "v2_1_apbt_four_breed_candidate_eval"
               / "four_group_validation_predictions.csv")
    ambull_top1 = ambull_trig = 0
    if val_csv.exists():
        with val_csv.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row["top1_label"] == AMBULL:
                    ambull_top1 += 1
                    if row["triggered_4"] == "True":
                        ambull_trig += 1
    record("val 中 AmBull 作 Top-1 的真实样本统计（信息项）", True,
           f"{ambull_top1} 张 Top-1=AmBull，其中触发 {ambull_trig} 张"
           f"（0 表示 val 无该 Top-1 的触发样本，非缺陷）")

    # ================= 输出 =================
    csv_path = out_dir / f"same_image_repeated_requests_{tag}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(repeated_rows[0].keys()))
        writer.writeheader()
        writer.writerows(repeated_rows)
    print()
    print(f"[accept] wrote {csv_path}")

    passed = sum(1 for c in CHECKS if c["passed"])
    failed = [c for c in CHECKS if not c["passed"]]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "split_used": "validation only (test split never read)",
        "test_split_access_count": 0,
        "samples": {k: str(v) for k, v in SAMPLES.items()},
        "checks": CHECKS,
        "passed": passed,
        "total": len(CHECKS),
        "failed": failed,
    }
    json_path = out_dir / f"acceptance_v2_1_{tag}.json"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    print(f"[accept] wrote {json_path}")
    print()
    print(f"[accept] {passed}/{len(CHECKS)} 项通过，失败 {len(failed)} 项")
    for item in failed:
        print(f"    FAIL: {item['check']} — {item['detail']}")
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
