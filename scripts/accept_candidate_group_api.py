#!/usr/bin/env python
"""相近犬种候选组的隔离环境 API 集成验收（只读数据，不训练）。

用法（在仓库根目录执行）::

    python scripts/accept_candidate_group_api.py

在**隔离环境**中跑真实链路：

* 临时 SQLite（``tmp`` 目录）+ 临时 uploads；
* 真实 ``PredictorService``，``weights_path`` 指向
  ``artifacts/v2_1_136classes_seed42/best_model.pth``（V2.1 候选模型）；
* 通过 ``fastapi.testclient.TestClient`` 发真实 ``POST /api/predict`` 请求，
  上传**原图**。

验收项：

A. 触发样本：``candidate_group.triggered`` 为真、三项候选中文名正确、
   组内得分和≈100、``predictions[0]`` 与导出清单一致且分数未被篡改；
B. 未触发样本：响应不含候选组或 ``triggered`` 为假，``predictions`` 正常；
C. 数据库：``predicted_breed``/``confidence``/``top_k_json`` 与响应一致，
   且**没有任何候选组字段入库**；
D. 关闭开关（``candidate_group_enabled=False``）：响应恢复原有形态，
   ``predictions`` 与开启时完全一致。

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
from PIL import Image  # noqa: E402

from backend.app.config import Settings  # noqa: E402
from backend.app.main import create_app  # noqa: E402
from backend.app.services.predictor import PredictorService  # noqa: E402

DEFAULT_MODEL_DIR = _REPO_ROOT / "artifacts" / "v2_1_136classes_seed42"
DEFAULT_OUT = _REPO_ROOT / "reports" / "v2_1_candidate_ui_review"
TRIGGERS_CSV = "val_candidate_triggers.csv"

CANDIDATE_ZH = {
    "american_staffordshire_terrier": "美国斯塔福郡梗",
    "staffordshire_bull_terrier": "斯塔福郡斗牛梗",
    "american_bulldog": "美国斗牛犬",
}

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
    """构造隔离 app；调用方需以 ``with TestClient(app)`` 方式驱动 lifespan。"""
    settings = make_settings(workdir, enabled)
    service = PredictorService(
        weights_path=settings.weights_path, device=settings.device,
        class_names_path=DEFAULT_MODEL_DIR / "class_names.json",
        candidate_group_enabled=settings.candidate_group_enabled)
    return create_app(settings=settings, predictor=service)


def post_image(client: TestClient, image_path: Path, top_k: int = 3) -> dict:
    """上传**原始字节**（不重新编码），保证与导出清单的推理输入完全一致。"""
    data = image_path.read_bytes()
    response = client.post(
        "/api/predict",
        files={"file": (image_path.name, data, "image/jpeg")},
        data={"top_k": str(top_k)})
    assert response.status_code == 200, (
        f"{image_path}: HTTP {response.status_code} {response.text[:300]}")
    return response.json()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--control-count", type=int, default=3,
                        help="number of non-triggered control images to test")
    args = parser.parse_args(argv)

    out_dir: Path = args.out_dir
    triggers_path = out_dir / TRIGGERS_CSV
    if not triggers_path.exists():
        print(f"[accept] missing {triggers_path}", file=sys.stderr)
        return 1
    with triggers_path.open(encoding="utf-8") as handle:
        triggered = list(csv.DictReader(handle))
    print(f"[accept] triggered images from validation: {len(triggered)}")

    # 未触发对照：取若干 val 图片（真实标签非候选组、且不在触发清单中）
    val_dir = _REPO_ROOT / "data" / "v2_processed" / "val"
    triggered_paths = {row["image_path"] for row in triggered}
    controls = []
    for path in sorted(val_dir.rglob("*.jpg")):
        if str(path) in triggered_paths:
            continue
        if path.parent.name in CANDIDATE_ZH:
            continue
        controls.append(path)
        if len(controls) >= args.control_count:
            break
    print(f"[accept] control (non-triggered) images: {len(controls)}")

    evidence: dict = {"triggered": [], "controls": []}

    # ================= A. 触发样本 =================
    print()
    print("=== A. 触发样本（开关开启）===")
    with tempfile.TemporaryDirectory(prefix="u6_accept_on_", ignore_cleanup_errors=True) as tmp:
        with TestClient(build_app(Path(tmp), enabled=True)) as client:
            for row in triggered:
                image_path = Path(row["image_path"])
                payload = post_image(client, image_path)
                group = payload.get("candidate_group")
                evidence["triggered"].append(
                    {"image": row["image_path"], "response": payload})

                record(f"{image_path.parent.name}/{image_path.name} 触发",
                       group is not None and group.get("triggered") is True,
                       f"reason={group.get('reason') if group else 'None'}")

                names = {item["breed"]: item for item in group["candidates"]}
                record("  三项候选齐全且中文名正确",
                       set(names) == set(CANDIDATE_ZH)
                       and all(names[k]["breed_zh"] == v
                               for k, v in CANDIDATE_ZH.items()))

                total = sum(item["group_score"] for item in group["candidates"])
                record("  组内得分和 ≈ 100", abs(total - 100.0) <= 1e-6,
                       f"sum={total}")

                record("  原始 Top-1 与清单一致",
                       payload["predictions"][0]["breed"] == row["top1_breed"],
                       f"{payload['predictions'][0]['breed']} vs "
                       f"{row['top1_breed']}")

                record("  原始 Top-1 分数与清单一致（GPU 非确定性容差 1e-3）",
                       abs(payload["predictions"][0]["confidence"]
                           - float(row["top1_confidence"])) <= 1e-3,
                       f"{payload['predictions'][0]['confidence']} vs "
                       f"{row['top1_confidence']}")

                # 精确检查：候选组里的 top1_confidence 必须与原始 Top-K 第一项
                # 完全相同——这是"没有为展示效果篡改概率"的硬证据。
                record("  候选组 top1_confidence 与原始 Top-1 完全一致",
                       abs(group["top1_confidence"]
                           - payload["predictions"][0]["confidence"]) <= 1e-9,
                       f"{group['top1_confidence']} vs "
                       f"{payload['predictions'][0]['confidence']}")

                # 精确检查：组内得分必须严格等于各自原始概率归一化
                mass = sum(item["original_confidence"]
                           for item in group["candidates"])
                record("  original_confidence 之和 = group_mass",
                       abs(mass - group["group_mass"]) <= 1e-6,
                       f"{mass} vs {group['group_mass']}")
                normalised_ok = all(
                    abs(item["group_score"]
                        - item["original_confidence"]
                        / group["group_mass"] * 100) <= 1e-3
                    for item in group["candidates"])
                record("  组内得分均等于原始概率归一化", normalised_ok)

                # 数据库字段核对
                db_path = Path(tmp) / "app.db"
                import sqlite3
                conn = sqlite3.connect(str(db_path))
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
                       row_db[0] == payload["predictions"][0]["breed"]
                       and abs(row_db[1]
                               - payload["predictions"][0]["confidence"])
                       <= 1e-6,
                       f"db={row_db[0]}/{row_db[1]}")

    # ================= B. 未触发对照 =================
    print()
    print("=== B. 未触发对照（开关开启）===")
    with tempfile.TemporaryDirectory(prefix="u6_accept_ctrl_", ignore_cleanup_errors=True) as tmp:
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
    with tempfile.TemporaryDirectory(prefix="u6_accept_off_", ignore_cleanup_errors=True) as tmp:
        with TestClient(build_app(Path(tmp), enabled=False)) as client:
            for row in triggered:
                image_path = Path(row["image_path"])
                payload = post_image(client, image_path)
                record(f"{image_path.parent.name}/{image_path.name} "
                       f"关闭后无候选组",
                       "candidate_group" not in payload
                       or payload.get("candidate_group") is None,
                       f"keys={sorted(payload.keys())}")
                record("  关闭后 Top-1 与开启时一致",
                       payload["predictions"][0]["breed"] == row["top1_breed"],
                       payload["predictions"][0]["breed"])
                evidence.setdefault("switch_off", []).append(
                    {"image": row["image_path"], "response": payload})

    # ================= 汇总 =================
    passed = sum(1 for c in CHECKS if c["passed"])
    failed = [c for c in CHECKS if not c["passed"]]
    print()
    print(f"[accept] {passed}/{len(CHECKS)} 项通过，失败 {len(failed)} 项")
    for item in failed:
        print(f"    FAIL: {item['check']} — {item['detail']}")

    evidence_path = out_dir / "acceptance_api_responses.json"
    evidence_path.write_text(
        json.dumps({"checks": CHECKS, "passed": passed,
                    "total": len(CHECKS), "evidence": evidence},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[accept] wrote {evidence_path}")
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
