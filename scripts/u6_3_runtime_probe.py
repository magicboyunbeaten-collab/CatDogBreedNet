#!/usr/bin/env python
"""U6.3 阶段 A2：默认启动行为的**运行期**取证（隔离实例，不写正式数据）。

用法（在仓库根目录执行）::

    python scripts/u6_3_runtime_probe.py                 # 默认配置实例
    python scripts/u6_3_runtime_probe.py --switch off    # 显式关闭对照实例

设计要点
--------
* **不修改任何配置文件或启动脚本**。只通过 ``CATDOG_DB_PATH`` /
  ``CATDOG_UPLOAD_DIR`` 把存储重定向到报告目录下的 ``runtime_*`` 子目录，
  其余配置完全走 ``Settings.from_env()`` 的默认解析路径——与日常启动入口
  （``启动后端.bat`` → ``uvicorn backend.app.main:app``）同一套逻辑。
* 上传**原始字节**（``read_bytes()``），不重新编码，避免概率漂移。
* 样本路径全部从既有 CSV 解析并断言存在；**缺失则如实记录，不编造、不替换**。
* 只读 ``data/v2_processed/val``；脚本内不含任何 test 路径。

产出（``reports/u6_3_default_runtime_and_freeze/``）：

* ``default_runtime_samples.csv`` —— 逐样本取证
* ``api_health_default.json`` / ``api_health_off.json``
* ``runtime_launcher_<tag>.log`` —— 启动 stderr（含模型身份证据）
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT_DIR = REPO / "reports" / "u6_3_default_runtime_and_freeze"
VAL = REPO / "data" / "v2_processed" / "val"
PORT = 8000
BASE = f"http://127.0.0.1:{PORT}"

FOUR = ("american_pit_bull_terrier", "american_staffordshire_terrier",
        "staffordshire_bull_terrier", "american_bulldog")


@dataclass
class Sample:
    group: str
    true_label: str
    image_path: Path
    expected: str          # trigger / non-trigger / control
    note: str = ""
    source_csv: str = ""


def resolve_samples() -> list[Sample]:
    """从既有 CSV 解析样本；路径缺失时记录 missing，不编造。"""
    samples: list[Sample] = []
    missing: list[str] = []

    def add(group, true_label, rel, expected, note, source):
        path = VAL / rel
        if path.exists():
            samples.append(Sample(group, true_label, path, expected, note,
                                  source))
        else:
            missing.append(f"{group}: {rel}")

    # --- collie-pair 触发（3 张，来自 U6.2 扫描明细）---
    scan = OUT_DIR.parent / "u6_2_collie_pair_candidate" \
        / "validation_trigger_samples.csv"
    pair_rows = list(csv.DictReader(scan.open(encoding="utf-8")))
    triggered = [r for r in pair_rows
                 if float(r["pair_mass"]) >= 0.30
                 and float(r["pair_margin"]) <= 0.30]
    for row in triggered:
        rel = row["image_path"].split("val/", 1)[1]
        add("collie-pair-trigger", row["true_label"], rel, "trigger",
            f"margin={float(row['pair_margin']):.4f}",
            scan.name)

    # --- collie-pair 不触发（Top-1 属两类但分差超阈值，真实标签在组外）---
    for want_label, want_top1 in (("afghan_hound", "collie"),
                                  ("bernese_mountain_dog",
                                   "border_collie")):
        for row in pair_rows:
            if (row["true_label"] == want_label
                    and row["top1_label"] == want_top1
                    and float(row["pair_margin"]) > 0.30):
                rel = row["image_path"].split("val/", 1)[1]
                add("collie-pair-non-trigger", row["true_label"], rel,
                    "non-trigger",
                    f"top1={want_top1} margin="
                    f"{float(row['pair_margin']):.4f}",
                    scan.name)
                break

    # --- 四类 bully 触发 ---
    bully_csv = (REPO / "reports" / "v2_1_apbt_four_breed_candidate_eval"
                 / "newly_triggered_by_apbt.csv")
    for row in csv.DictReader(bully_csv.open(encoding="utf-8")):
        if row.get("triggered_4") == "True":
            path = Path(row["image_path"])
            if path.exists():
                samples.append(Sample(
                    "four-breed-trigger", row["true_label"], path, "trigger",
                    f"mass={float(row['group_mass_4']):.4f} "
                    f"margin={float(row['group_margin_4']):.4f}",
                    bully_csv.name))
            else:
                missing.append(f"four-breed-trigger: {row['image_path']}")

    # --- 四类 bully 不触发（Top-1 在四类内但分差超阈值）---
    preds_csv = (REPO / "reports" / "v2_1_apbt_four_breed_candidate_eval"
                 / "four_group_validation_predictions.csv")
    for row in csv.DictReader(preds_csv.open(encoding="utf-8")):
        if (row["top1_label"] in FOUR and row.get("triggered_4") != "True"):
            path = Path(row["image_path"])
            if path.exists():
                samples.append(Sample(
                    "four-breed-non-trigger", row["true_label"], path,
                    "non-trigger",
                    f"top1={row['top1_label']} "
                    f"margin={float(row['group_margin_4']):.4f}",
                    preds_csv.name))
                break

    # --- 对照组：不属于任何候选组 ---
    beagle_dir = VAL / "beagle"
    first = sorted(beagle_dir.glob("*.jpg"))[0]
    samples.append(Sample("control", "beagle", first, "control",
                          "不属于任何候选组", "val/beagle"))

    if missing:
        print(f"[A2] 缺失样本（未替换）：{missing}")
    return samples


def wait_ready(timeout: float = 90.0) -> dict | None:
    import requests
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = requests.get(f"{BASE}/api/health", timeout=5)
            if response.status_code == 200:
                return response.json()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    return None


def probe(runtime_dir: Path, tag: str, override_test: bool,
          samples: list[Sample]) -> tuple[list[dict], dict, Path]:
    """起一个隔离实例并逐样本上传取证。"""
    runtime_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["CATDOG_DB_PATH"] = str(runtime_dir / "app.db")
    env["CATDOG_UPLOAD_DIR"] = str(runtime_dir / "uploads")
    if override_test:
        env["CATDOG_CANDIDATE_GROUP_ENABLED"] = "false"
    else:
        env.pop("CATDOG_CANDIDATE_GROUP_ENABLED", None)
    env.pop("CATDOG_WEIGHTS_PATH", None)
    env.pop("CATDOG_CLASS_NAMES_PATH", None)

    log_path = OUT_DIR / f"runtime_launcher_{tag}.log"
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.app.main:app",
         "--port", str(PORT)],
        cwd=str(REPO), env=env, stdout=log_handle,
        stderr=subprocess.STDOUT, text=True)
    print(f"[A2] {tag}: pid={process.pid} "
          f"db={env['CATDOG_DB_PATH']} "
          f"uploads={env['CATDOG_UPLOAD_DIR']} "
          f"candidate_override={'false' if override_test else '(默认)'}")
    try:
        health = wait_ready()
        if health is None:
            raise RuntimeError(f"{tag}: /api/health 未在超时内就绪")
        (OUT_DIR / f"api_health_{tag}.json").write_text(
            json.dumps(health, indent=2, ensure_ascii=False),
            encoding="utf-8")
        print(f"[A2] {tag}: health -> num_classes={health.get('num_classes')} "
              f"model_weights={health.get('model_weights')} "
              f"model_loaded={health.get('model_loaded')}")

        import requests
        rows: list[dict] = []
        for sample in samples:
            data = sample.image_path.read_bytes()
            response = requests.post(
                f"{BASE}/api/predict",
                files={"file": (sample.image_path.name, data, "image/jpeg")},
                data={"top_k": "3"}, timeout=120)
            if response.status_code != 200:
                rows.append({
                    "instance": tag, "override_test": override_test,
                    "group": sample.group, "true_label": sample.true_label,
                    "image_path": str(sample.image_path), "expected":
                    sample.expected, "note": sample.note,
                    "error": f"HTTP {response.status_code}",
                })
                continue
            payload = response.json()
            group = payload.get("candidate_group") or {}
            rows.append({
                "instance": tag,
                "override_test": override_test,
                "group": sample.group,
                "true_label": sample.true_label,
                "image_path": str(sample.image_path),
                "expected": sample.expected,
                "note": sample.note,
                "source_csv": sample.source_csv,
                "num_classes": payload.get("num_classes"),
                "top1_label": payload["predictions"][0]["breed"],
                "top1_probability": payload["predictions"][0]["confidence"],
                "topk_labels": ";".join(
                    p["breed"] for p in payload["predictions"]),
                "topk_scores": ";".join(
                    f"{p['confidence']:.8f}" for p in payload["predictions"]),
                "candidate_group_id": group.get("group_id"),
                "triggered": group.get("triggered"),
                "trigger_reason": group.get("reason"),
                "threshold_version": group.get("threshold_version"),
                "group_mass": group.get("group_mass"),
                "group_margin": group.get("group_margin"),
                "candidate_scores": ";".join(
                    f"{c['breed']}={c['group_score']:.4f}"
                    for c in group.get("candidates", [])),
                "exposes_probabilities": "probabilities" in payload,
            })
        return rows, health, log_path
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
        log_handle.close()
        print(f"[A2] {tag}: 进程已停止，日志 {log_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--switch", choices=("default", "off"),
                        default="default")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    samples = resolve_samples()
    print(f"[A2] 解析到 {len(samples)} 张 validation 样本：")
    for sample in samples:
        print(f"     {sample.group:<24} {sample.true_label:<24} "
              f"{sample.image_path.name}")

    override = args.switch == "off"
    tag = "off" if override else "default"
    runtime_dir = OUT_DIR / f"runtime_{tag}"
    rows, health, log_path = probe(runtime_dir, tag, override, samples)

    # 追加写入同一份 CSV（两个实例共用表头）
    csv_path = OUT_DIR / "default_runtime_samples.csv"
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    write_header = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields,
                                extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(rows)
    print(f"[A2] wrote {csv_path}（{len(rows)} 行）")

    triggered = [r for r in rows if r.get("triggered") is True]
    print(f"[A2] {tag}: 触发 {len(triggered)} 张 / 共 {len(rows)} 张")
    for row in rows:
        marker = "TRIGGER" if row.get("triggered") else "  ---  "
        print(f"     [{marker}] {row['group']:<24} "
              f"top1={row.get('top1_label')} "
              f"group_id={row.get('candidate_group_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
