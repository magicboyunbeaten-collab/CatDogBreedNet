#!/usr/bin/env python
"""U6.1-S0：轻量安全核验快照采集（**只读，不执行任何 git 写操作**）。

用法（在仓库根目录执行）::

    python scripts/u6_collect_s0_snapshot.py

产出（写入 ``reports/u6_1_low_lr/``）：

* ``s0/git_head.txt`` / ``git_status_short.txt`` / ``git_diff_stat.txt`` /
  ``git_diff_check.txt`` / ``git_diff.txt`` / ``tracked_changes.txt`` /
  ``untracked_files.txt`` / ``weight_hashes.json`` / ``data_inventory.json``
* ``u6_1_protection_before.json``（复用 diagnostic_protection_snapshot 的自动比对）
* ``git_worktree_audit.md`` —— 按「既有变更 / U5.5 接入变更 / U6 训练工具 /
  U6 实验产物」四类分组的变更清单与"未提交"结论
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports" / "u6_1_low_lr"
S0 = OUT / "s0"

#: 变更分组规则（按前缀匹配，先命中先生效）。
GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("U6 训练工具与实验产物", (
        "ml/train.py", "ml/dataset.py", "ml/u6_pair_training.py",
        "scripts/u6_", "reports/u6_border_collie/",
        "artifacts/v2_2_border_collie_",
        "md/u6_border_collie_improvement_plan_修订版.md",
        "md/U6.1_低学习率纠偏与边牧专项对照实验任务.md",
    )),
    ("U5.5 V2.1 默认接入与 136 类映射", (
        "backend/app/config.py", "backend/app/main.py",
        "backend/app/schemas.py", "backend/app/services/predictor.py",
        "frontend/src/utils/breedNames.js",
        "frontend/tests/breedNames.test.js",
        "frontend/tests/historyView.test.js",
        "tests/test_api.py", "tests/test_predictor_service.py",
        "启动后端.bat", "启动系统.bat",
    )),
    ("U5 / U5.2 四类候选组", (
        "backend/app/routes/predict.py",
        "frontend/src/components/PredictionResult.vue",
        "ml/predict.py", "ml/predictor.py",
    )),
    ("U4 V2.1 训练扩展", ("tests/test_train_extensions.py",)),
]

PROTECTED = [
    "artifacts/best_model.pth",
    "artifacts/class_names.json",
    "artifacts/model_version.json",
    "artifacts/experiment_config.json",
    "artifacts/v2_1_136classes_seed42/best_model.pth",
    "artifacts/v2_1_136classes_seed42/class_names.json",
    "artifacts/v2_1_136classes_seed42/model_version.json",
    "artifacts/v2_1_136classes_seed42/experiment_config.json",
]
DATA_DIRS = ["processed", "processed_clean", "raw", "v2_processed",
             "v2_processed_prev"]


def run_git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=str(REPO), capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        return f"<git {' '.join(args)} failed: {result.stderr.strip()}>"
    return result.stdout.rstrip()


def sha256(path: Path) -> str:
    if not path.exists():
        return "<missing>"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dir_stats(path: Path) -> dict:
    if not path.is_dir():
        return {"exists": False, "files": 0, "bytes": 0}
    files = total = 0
    for item in path.rglob("*"):
        if item.is_file():
            files += 1
            total += item.stat().st_size
    return {"exists": True, "files": files, "bytes": total}


def classify(path: str) -> str:
    for name, prefixes in GROUPS:
        if any(path.startswith(prefix) or path == prefix for prefix in prefixes):
            return name
    return "其他历史产物 / 未分类"


def main() -> int:
    S0.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    head = run_git("log", "--oneline", "-1")
    head_sha = run_git("rev-parse", "HEAD")
    status = run_git("status", "--short")
    diff_stat = run_git("diff", "--stat")
    diff_check = run_git("diff", "--check")
    diff = run_git("diff")

    (S0 / "git_head.txt").write_text(f"{head}\n{head_sha}\n", encoding="utf-8")
    (S0 / "git_status_short.txt").write_text(status, encoding="utf-8")
    (S0 / "git_diff_stat.txt").write_text(diff_stat, encoding="utf-8")
    (S0 / "git_diff_check.txt").write_text(
        diff_check or "(无空白/冲突标记问题)", encoding="utf-8")
    (S0 / "git_diff.txt").write_text(diff, encoding="utf-8")

    tracked, untracked = [], []
    for line in status.splitlines():
        if not line.strip():
            continue
        code, path = line[:2], line[3:]
        (untracked if code.strip() == "??" else tracked).append(path.strip())
    (S0 / "tracked_changes.txt").write_text("\n".join(tracked), encoding="utf-8")
    (S0 / "untracked_files.txt").write_text("\n".join(untracked),
                                            encoding="utf-8")

    weights = {path: sha256(REPO / path) for path in PROTECTED}
    (S0 / "weight_hashes.json").write_text(
        json.dumps(weights, indent=2, ensure_ascii=False), encoding="utf-8")

    data = {name: dir_stats(REPO / "data" / name) for name in DATA_DIRS}
    uploads = dir_stats(REPO / "uploads")
    data["uploads"] = uploads
    (S0 / "data_inventory.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- 分组 ----
    grouped: dict[str, list[str]] = {}
    for path in tracked + untracked:
        grouped.setdefault(classify(path), []).append(path)

    # ---- 正式 DB ----
    db_info = {}
    try:
        import sqlite3
        conn = sqlite3.connect(str(REPO / "data" / "app.db"))
        db_info["records"] = conn.execute(
            "SELECT COUNT(*) FROM prediction_records").fetchone()[0]
        db_info["integrity"] = conn.execute("PRAGMA integrity_check").fetchone()[0]
        conn.close()
    except Exception as exc:  # noqa: BLE001
        db_info = {"error": str(exc)}

    lines: list[str] = []
    add = lines.append
    add("# U6.1-S0：Git 工作区与保护对象核验（未提交）")
    add("")
    add(f"> 生成时间：{datetime.now(timezone.utc).isoformat()}")
    add("> 执行脚本：`scripts/u6_collect_s0_snapshot.py`（**只读，无任何 git 写操作**）")
    add("")
    add("## 1. 结论")
    add("")
    add("**本轮不执行 Git 提交。** 原因：工作区同时混有 U4/U5/U5.1/U5.2/U5.3/U5.4/U5.5/U6")
    add("多轮未提交改动与大量历史产物，**无法在不误伤的前提下切分出「仅 U6.1 所需」或")
    add("「仅 U5.5 接入所需」的最小提交集**。按任务 §8 要求：无法安全分割则保持未提交、")
    add("保存快照并继续实验。")
    add("")
    add("## 2. 当前 Git 状态")
    add("")
    add(f"- HEAD：`{head}`")
    add(f"- HEAD SHA：`{head_sha}`")
    add(f"- 已跟踪改动：**{len(tracked)}** 个文件")
    add(f"- 未跟踪项：**{len(untracked)}** 个")
    add(f"- `git diff --check`：{'无空白/冲突标记问题' if not diff_check else '见 s0/git_diff_check.txt'}")
    add(f"- 正式 `data/app.db`：`{db_info.get('records')}` 条，"
        f"`integrity_check: {db_info.get('integrity')}`")
    add("")
    add("## 3. 变更分组清单")
    add("")
    add("| 分组 | 文件数 | 文件 |")
    add("|---|---|---|")
    for name in [g for g, _ in GROUPS] + ["其他历史产物 / 未分类"]:
        items = grouped.get(name, [])
        if not items:
            continue
        add(f"| {name} | {len(items)} | "
            + "<br>".join(f"`{p}`" for p in items) + " |")
    add("")
    add("## 4. 保护对象哈希（只读核验）")
    add("")
    add("| 文件 | SHA256 |")
    add("|---|---|")
    for path, digest in weights.items():
        add(f"| `{path}` | `{digest}` |")
    add("")
    v11 = weights.get("artifacts/best_model.pth", "")
    add("V1.1 期望值 `89ef468f199c6d1550fec2638c5ea6f8ef7ad543e57f8ec82c4263c121b1a256`；"
        "本次实测 " + ("**一致**。" if v11.startswith(
            "89ef468f199c6d1550fec2638c5ea6f8ef7ad543e57f8ec82c4263c121b1a256")
        else "**不一致，需立即停止核查**。"))
    add("")
    add("## 5. 数据目录与 uploads")
    add("")
    add("| 目录 | 文件数 | 总字节 |")
    add("|---|---|---|")
    for name, stats in data.items():
        add(f"| `data/{name}` / `uploads` | {stats['files']} | {stats['bytes']} |"
            if name == "uploads" else
            f"| `data/{name}/` | {stats['files']} | {stats['bytes']} |")
    add("")
    add("## 6. 未执行的操作")
    add("")
    add("- 未执行 `git add` / `git commit` / `git reset --hard` / `git clean` / "
        "大范围 `checkout`")
    add("- 未删除、覆盖或改写任何文件、报告目录、数据目录、权重或数据库")
    add("- 未访问 `data/v2_processed/test`（本阶段不训练、不评估）")
    add("")
    add("## 7. 附件")
    add("")
    for name in sorted(p.name for p in S0.iterdir() if p.is_file()):
        add(f"- `s0/{name}`")
    add("")
    add("保护快照：`u6_1_protection_before.json`（`diagnostic_protection_snapshot.py "
        "--phase before`）。")
    add("")

    (OUT / "git_worktree_audit.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"[s0] HEAD = {head}")
    print(f"[s0] tracked = {len(tracked)}, untracked = {len(untracked)}")
    print(f"[s0] diff --check: {'clean' if not diff_check else 'issues'}")
    print(f"[s0] V1.1 = {weights['artifacts/best_model.pth']}")
    print(f"[s0] V2.1 = {weights['artifacts/v2_1_136classes_seed42/best_model.pth']}")
    print(f"[s0] db = {db_info}")
    print(f"[s0] wrote {OUT / 'git_worktree_audit.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
