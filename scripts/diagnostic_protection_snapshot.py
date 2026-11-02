#!/usr/bin/env python
"""诊断前后保护快照：只读计算摘要，供比对"未改动任何受保护对象"。

用法::

    python scripts/diagnostic_protection_snapshot.py --phase before
    python scripts/diagnostic_protection_snapshot.py --phase after

`--phase after` 会自动与 `before` 快照逐项比对；任何不一致都会以非零码退出
并列出差异（不自动修复、不回退）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

OUT_DIR = _REPO_ROOT / "reports" / "v2_1_diagnostics"

WATCHED_FILES = [
    "artifacts/best_model.pth",                 # V1.1 正式
    "artifacts/last_model.pth",
    "artifacts/class_names.json",
    "artifacts/model_version.json",
    "artifacts/experiment_config.json",
    "artifacts/v2_1_136classes_seed42/best_model.pth",
    "artifacts/v2_1_136classes_seed42/last_model.pth",
    "artifacts/v2_1_136classes_seed42/class_names.json",
    "artifacts/v2_1_136classes_seed42/experiment_config.json",
]
WATCHED_DIRS = [
    "data/processed",
    "data/processed_clean",
    "data/raw",
    "data/v2_processed",
    "data/v2_processed_prev",
]

#: V1.1 正式 checkpoint 的期望 SHA256（任务单给定）。
EXPECTED_V11_SHA256 = (
    "89ef468f199c6d1550fec2638c5ea6f8ef7ad543e57f8ec82c4263c121b1a256")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dir_stats(root: Path) -> dict:
    files = [p for p in root.rglob("*") if p.is_file()]
    return {"files": len(files), "bytes": sum(p.stat().st_size for p in files)}


def git_state() -> dict:
    def run(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args], cwd=str(_REPO_ROOT), capture_output=True,
                text=True, encoding="utf-8", errors="replace", check=False,
            ).stdout.strip()
        except Exception as exc:  # noqa: BLE001
            return f"<git error: {exc}>"

    return {
        "head": run("log", "-1", "--oneline"),
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
        "status_short": run("-c", "core.quotepath=false", "status", "--short"),
    }


def build_snapshot() -> dict:
    snapshot = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "git": git_state(),
        "files": {},
        "dirs": {},
    }
    for name in WATCHED_FILES:
        path = Path(name)
        if path.exists():
            snapshot["files"][name] = {
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        else:
            snapshot["files"][name] = {"missing": True}
    for name in WATCHED_DIRS:
        path = Path(name)
        snapshot["dirs"][name] = (dir_stats(path) if path.is_dir()
                                  else {"missing": True})

    conn = sqlite3.connect(str(_REPO_ROOT / "data" / "app.db"))
    snapshot["database"] = {
        "records": conn.execute(
            "select count(*) from prediction_records").fetchone()[0],
        "integrity": conn.execute("pragma integrity_check").fetchone()[0],
    }
    conn.close()
    snapshot["uploads"] = {
        "count": len([p for p in (_REPO_ROOT / "uploads").glob("*")
                      if p.is_file()])}
    return snapshot


def compare(before: dict, after: dict) -> list[str]:
    diffs: list[str] = []
    for name, expected in before["files"].items():
        actual = after["files"].get(name, {})
        if expected.get("missing") or actual.get("missing"):
            if expected.get("missing") != actual.get("missing"):
                diffs.append(f"文件存在性变化: {name}")
            continue
        if expected["sha256"] != actual["sha256"]:
            diffs.append(
                f"文件哈希变化: {name} "
                f"({expected['sha256'][:16]} -> {actual['sha256'][:16]})")
    for name, expected in before["dirs"].items():
        actual = after["dirs"].get(name, {})
        if expected.get("missing") or actual.get("missing"):
            if expected.get("missing") != actual.get("missing"):
                diffs.append(f"目录存在性变化: {name}")
            continue
        if expected["files"] != actual["files"]:
            diffs.append(f"文件数变化: {name} "
                         f"{expected['files']} -> {actual['files']}")
        if expected["bytes"] != actual["bytes"]:
            diffs.append(f"字节数变化: {name} "
                         f"{expected['bytes']} -> {actual['bytes']}")
    if before["database"] != after["database"]:
        diffs.append(f"数据库变化: {before['database']} -> "
                     f"{after['database']}")
    if before["uploads"] != after["uploads"]:
        diffs.append(f"uploads 变化: {before['uploads']} -> "
                     f"{after['uploads']}")
    return diffs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--phase", choices=["before", "after"],
                        required=True)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR,
                        help="输出目录；默认沿用 reports/v2_1_diagnostics "
                             "（既有行为不变），新诊断任务可指向独立目录")
    args = parser.parse_args(argv)

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()

    # V1.1 正式 checkpoint 期望值核对（只在 before 阶段强制）
    v11 = snapshot["files"]["artifacts/best_model.pth"]
    actual = v11.get("sha256")
    matches = actual == EXPECTED_V11_SHA256
    print(f"[snapshot] V1.1 best_model.pth sha256={actual}")
    print(f"[snapshot] 与任务单期望值一致: {matches}")
    if args.phase == "before" and not matches:
        print("[snapshot] ** V1.1 SHA256 与任务单不符，停止 **", file=sys.stderr)
        return 1

    path = out_dir / f"protection_snapshot_{args.phase}.json"
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    print(f"[snapshot] wrote {path}")

    if args.phase == "after":
        before_path = out_dir / "protection_snapshot_before.json"
        if not before_path.exists():
            print("[snapshot] 缺少 before 快照，无法比对", file=sys.stderr)
            return 1
        before = json.loads(before_path.read_text(encoding="utf-8"))
        diffs = compare(before, snapshot)
        if diffs:
            print(f"[snapshot] ** 发现 {len(diffs)} 项差异 **", file=sys.stderr)
            for item in diffs:
                print(f"  - {item}", file=sys.stderr)
            return 2
        print("[snapshot] 前后比对：全部受保护对象一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
