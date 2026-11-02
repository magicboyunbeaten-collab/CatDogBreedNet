#!/usr/bin/env python
"""U5.2 四类相近犬种候选组的隔离环境 API 集成验收（只读数据，不训练）。

用法（在仓库根目录执行）::

    python scripts/accept_four_breed_candidate_api.py

在**隔离环境**中跑真实链路：

* 临时 SQLite + 临时 uploads；
* 真实 ``PredictorService``，``weights_path`` 指向 V2.1 候选权重；
* 通过 ``fastapi.testclient.TestClient`` 发真实 ``POST /api/predict``，
  上传**原始图片字节**（不重新编码）。

样本来源（**全部来自 validation split**，test split 访问记录为 0）：

* U5.1 ``reports/v2_1_apbt_four_breed_candidate_eval/newly_triggered_by_apbt.csv``
  —— 三类不触发但四类触发的代表性样本（本任务验收重点）；
* 同目录 ``triggered_by_both_strategies.csv`` —— 两类策略都触发的样本；
* 同目录 ``out_of_group_trigger_examples.csv`` —— 组外误触发样本；
* 另取若干未触发对照图。

验收项：四项候选齐全且中文名正确、组内得分和≈100、组内得分严格等于原始
概率归一化、候选 ``top1_confidence`` 与 ``predictions[0]`` 完全一致、
DB 表无候选组字段且记录与响应一致、关闭开关后无候选组。

正式模型默认路径与 ``artifacts/best_model.pth`` 全程不被触碰；
``data/app.db`` 与 ``uploads/`` 不被使用。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.config import Settings  # noqa: E402
from backend.app.main import create_app  # noqa: E402
from backend.app.services.candidate_group import (  # noqa: E402
    CANDIDATE_GROUP,
    CANDIDATE_GROUP_ZH,
    THRESHOLD_VERSION,
)
from backend.app.services.predictor import PredictorService  # noqa: E402

DEFAULT_MODEL_DIR = _REPO_ROOT / "artifacts" / "v2_1_136classes_seed42"
DEFAULT_OUT = (_REPO_ROOT
               / "reports" / "v2_1_four_breed_candidate_implementation")
U51_DIR = _REPO_ROOT / "reports" / "v2_1_apbt_four_breed_candidate_eval"
DEFAULT_VAL_DIR = _REPO_ROOT / "data" / "v2_processed" / "val"

CHECKS: list[dict] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    CHECKS.append({"check": name, "passed": bool(passed), "detail": detail})
    mark = "PASS" if passed else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))


def make_settings(workdir: Path, enabled: bool) -> Settings:
    return Settings(
        weights_path=DEFAULT_MODEL_DIR / "best_model.pth",
        device="auto",
        upload_dir=workdir / "uploads",
        db_path=workdir / "app.db",
        cors_origins=["http://localhost:5173"],
        max_upload_bytes=10 * 1024 * 1024,
        max_image_pixels=25_000_000,
        candidate_group_enabled=enabled,
    )


def build_app(workdir: Path, enabled: bool):
    """构造隔离 app；调用方以 ``with TestClient(app)`` 驱动 lifespan。"""
    settings = make_settings(workdir, enabled)
    service = PredictorService(
        weights_path=settings.weights_path, device=settings.device,
        class_names_path=DEFAULT_MODEL_DIR / "class_names.json",
        candidate_group_enabled=settings.candidate_group_enabled)
    return create_app(settings=settings, predictor=service)


def post_image(client: TestClient, image_path: Path, top_k: int = 3) -> dict:
    """上传**原始字节**（不重新编码），保证与 U5.1 推理输入一致。"""
    data = image_path.read_bytes()
    response = client.post(
        "/api/predict",
        files={"file": (image_path.name, data, "image/jpeg")},
        data={"top_k": str(top_k)})
    assert response.status_code == 200, (
        f"{image_path}: HTTP {response.status_code} {response.text[:300]}")
    return response.json()


def load_sample(csv_name: str) -> list[dict]:
    path = U51_DIR / csv_name
    if not path.exists():
        print(f"[accept] 缺少 {path}", file=sys.stderr)
        return []
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def check_triggered(image_path: Path, payload: dict, group: dict,
                    expected: dict | None = None) -> None:
    label = f"{image_path.parent.name}/{image_path.name}"
    record(f"{label} 触发", group.get("triggered") is True,
           f"reason={group.get('reason')}")

    names = {item["breed"]: item for item in group["candidates"]}
    record("  四项候选齐全且中文名正确",
           set(names) == set(CANDIDATE_GROUP)
           and all(names[k]["breed_zh"] == v
                   for k, v in CANDIDATE_GROUP_ZH.items()))

    total = sum(item["group_score"] for item in group["candidates"])
    record("  组内得分和 ≈ 100", abs(total - 100.0) <= 1e-6, f"sum={total}")

    # 精确检查：组内得分必须严格等于各自原始概率归一化
    normalised_ok = all(
        abs(item["group_score"]
            - item["original_confidence"] / group["group_mass"] * 100) <= 1e-3
        for item in group["candidates"])
    record("  组内得分均等于原始概率归一化", normalised_ok)

    record("  候选 top1_confidence 与原始 Top-1 完全一致",
           abs(group["top1_confidence"]
               - payload["predictions"][0]["confidence"]) <= 1e-9,
           f"{group['top1_confidence']} vs "
           f"{payload['predictions'][0]['confidence']}")

    record("  阈值版本为 U5.2 四类 B1",
           group.get("threshold_version") == THRESHOLD_VERSION,
           group.get("threshold_version", ""))

    if expected is not None:
        # 与 U5.1 记录的代表性样本比对（GPU 跨批次容差 1e-3）
        record("  原始 Top-1 与 U5.1 清单一致",
               payload["predictions"][0]["breed"] == expected["top1_label"],
               f"{payload['predictions'][0]['breed']} vs "
               f"{expected['top1_label']}")
        record("  原始 Top-1 分数与 U5.1 一致（GPU 容差 1e-3）",
               abs(payload["predictions"][0]["confidence"]
                   - float(expected["top1_probability"])) <= 1e-3,
               f"{payload['predictions'][0]['confidence']} vs "
               f"{expected['top1_probability']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--val-dir", type=Path, default=DEFAULT_VAL_DIR)
    parser.add_argument("--control-count", type=int, default=3,
                        help="number of non-triggered control images to test")
    args = parser.parse_args(argv)

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- 样本清单（全部来自 validation）----
    newly = load_sample("newly_triggered_by_apbt.csv")
    both = load_sample("triggered_by_both_strategies.csv")
    out_of_group = load_sample("out_of_group_trigger_examples.csv")
    print(f"[accept] U5.1 代表性样本：newly_triggered {len(newly)} 张、"
          f"both {len(both)} 张、out_of_group {len(out_of_group)} 张")

    val_dir = args.val_dir
    known = {Path(r["image_path"]) for r in newly + both + out_of_group}
    controls = []
    for path in sorted(val_dir.rglob("*.jpg")):
        if path in known:
            continue
        if path.parent.name in CANDIDATE_GROUP:
            continue
        controls.append(path)
        if len(controls) >= args.control_count:
            break
    print(f"[accept] 未触发对照 {len(controls)} 张")

    evidence: dict = {"triggered": [], "controls": [], "switch_off": [],
                      "sample_rows": []}
    sample_fields = [
        "sample_id", "source", "split", "true_label", "top1_label",
        "top1_probability", "p_apbt", "p_amstaff", "p_sbt", "p_ambull",
        "group_mass_4", "group_margin_4", "triggered_3", "triggered_4",
        "reason", "image_path",
    ]

    def sample_row(row: dict, payload: dict, source: str) -> dict:
        group = payload.get("candidate_group") or {}
        candidates = {item["breed"]: item for item in group.get("candidates", [])}
        return {
            "sample_id": f"{Path(row['image_path']).parent.name}/"
                         f"{Path(row['image_path']).name}",
            "source": source,
            "split": "val",
            "true_label": row.get("true_label", ""),
            "top1_label": payload["predictions"][0]["breed"],
            "top1_probability": payload["predictions"][0]["confidence"],
            "p_apbt": candidates.get("american_pit_bull_terrier", {})
                .get("original_confidence", ""),
            "p_amstaff": candidates.get("american_staffordshire_terrier", {})
                .get("original_confidence", ""),
            "p_sbt": candidates.get("staffordshire_bull_terrier", {})
                .get("original_confidence", ""),
            "p_ambull": candidates.get("american_bulldog", {})
                .get("original_confidence", ""),
            "group_mass_4": group.get("group_mass", ""),
            "group_margin_4": group.get("group_margin", ""),
            "triggered_3": row.get("triggered_3", ""),
            "triggered_4": group.get("triggered", ""),
            "reason": group.get("reason", ""),
            "image_path": row["image_path"],
        }

    # ================= A. 代表性样本（开关开启）=================
    print()
    print("=== A. U5.1 代表性样本（开关开启）===")
    with tempfile.TemporaryDirectory(prefix="u52_on_",
                                     ignore_cleanup_errors=True) as tmp:
        with TestClient(build_app(Path(tmp), enabled=True)) as client:
            for source, rows, expect in (
                    ("newly_triggered_by_apbt", newly, True),
                    ("triggered_by_both", both, True),
                    ("out_of_group", out_of_group, True)):
                for row in rows:
                    image_path = Path(row["image_path"])
                    payload = post_image(client, image_path)
                    group = payload.get("candidate_group") or {}
                    evidence["triggered"].append(
                        {"image": row["image_path"], "response": payload,
                         "source": source})
                    evidence["sample_rows"].append(
                        sample_row(row, payload, source))
                    if expect:
                        check_triggered(image_path, payload, group,
                                        expected=row)
                    else:
                        record(f"{image_path.parent.name}/{image_path.name} "
                               f"未触发", group.get("triggered") is False)

    # ================= B. 未触发对照 =================
    print()
    print("=== B. 未触发对照（开关开启）===")
    with tempfile.TemporaryDirectory(prefix="u52_ctrl_",
                                     ignore_cleanup_errors=True) as tmp:
        with TestClient(build_app(Path(tmp), enabled=True)) as client:
            for image_path in controls:
                payload = post_image(client, image_path)
                group = payload.get("candidate_group")
                evidence["controls"].append(
                    {"image": str(image_path), "response": payload})
                record(f"{image_path.parent.name}/{image_path.name} 未触发",
                       group is None or group.get("triggered") is False,
                       f"reason={group.get('reason') if group else 'None'}")
                record("  原始 Top-K 仍正常返回",
                       len(payload["predictions"]) == 3
                       and payload["predictions"][0]["confidence"] > 0)

    # ================= C. 关闭开关 =================
    print()
    print("=== C. 关闭 CATDOG_CANDIDATE_GROUP_ENABLED ===")
    with tempfile.TemporaryDirectory(prefix="u52_off_",
                                     ignore_cleanup_errors=True) as tmp:
        with TestClient(build_app(Path(tmp), enabled=False)) as client:
            for row in newly + both:
                image_path = Path(row["image_path"])
                payload = post_image(client, image_path)
                record(f"{image_path.parent.name}/{image_path.name} "
                       f"关闭后无候选组",
                       "candidate_group" not in payload
                       or payload.get("candidate_group") is None,
                       f"keys={sorted(payload.keys())}")
                record("  关闭后 Top-1 与开启时一致",
                       payload["predictions"][0]["breed"] == row["top1_label"],
                       payload["predictions"][0]["breed"])
                evidence["switch_off"].append(
                    {"image": row["image_path"], "response": payload})

    # ================= D. 数据库字段核对 =================
    print()
    print("=== D. 数据库字段核对（隔离临时库）===")
    import sqlite3
    with tempfile.TemporaryDirectory(prefix="u52_db_",
                                     ignore_cleanup_errors=True) as tmp:
        with TestClient(build_app(Path(tmp), enabled=True)) as client:
            for row in (newly + both)[:1]:
                post_image(client, Path(row["image_path"]))
            conn = sqlite3.connect(str(Path(tmp) / "app.db"))
            columns = [r[1] for r in conn.execute(
                "PRAGMA table_info(prediction_records)")]
            row_db = conn.execute(
                "SELECT predicted_breed, confidence, top_k_json "
                "FROM prediction_records ORDER BY id DESC LIMIT 1").fetchone()
            conn.close()
            record("  DB 无候选组字段",
                   not any("candidate" in c.lower() for c in columns),
                   f"columns={columns}")
            record("  DB 记录与响应一致",
                   row_db is not None and row_db[0]
                   == evidence["triggered"][0]["response"]["predictions"][0]["breed"])

    # ================= 汇总 =================
    passed = sum(1 for c in CHECKS if c["passed"])
    failed = [c for c in CHECKS if not c["passed"]]
    print()
    print(f"[accept] {passed}/{len(CHECKS)} 项通过，失败 {len(failed)} 项")
    for item in failed:
        print(f"    FAIL: {item['check']} — {item['detail']}")

    evidence_path = out_dir / "acceptance_api_responses.json"
    evidence_path.write_text(
        json.dumps({"checks": CHECKS, "passed": passed, "total": len(CHECKS),
                    "threshold_version": THRESHOLD_VERSION,
                    "candidate_group": list(CANDIDATE_GROUP),
                    "evidence": evidence}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(f"[accept] wrote {evidence_path}")

    if evidence["sample_rows"]:
        csv_path = out_dir / "validation_samples_four_breed.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=sample_fields)
            writer.writeheader()
            writer.writerows(evidence["sample_rows"])
        print(f"[accept] wrote {csv_path}（{len(evidence['sample_rows'])} 行）")

    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
