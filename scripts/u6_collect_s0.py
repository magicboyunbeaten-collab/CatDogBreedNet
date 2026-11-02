#!/usr/bin/env python
"""U6-S0：轻量安全固化 —— 采集工作区快照与差异清单（**只读，不提交 Git**）。

用法（在仓库根目录执行）::

    python scripts/u6_collect_s0.py

产出（写入 ``reports/u6_border_collie/``）：

* ``s0/git_head.txt`` / ``s0/git_status_short.txt`` / ``s0/git_diff_stat.txt``
  / ``s0/git_diff_check.txt`` / ``s0/git_diff.txt``
* ``s0/tracked_changes.txt`` —— 已跟踪改动逐文件清单
* ``s0/untracked_files.txt`` —— 未跟踪项清单
* ``s0_u5_5_solidification.md`` —— 固化说明（含**未提交原因**与人工切分建议）

本脚本**不执行任何 git 写操作**（无 add / commit / reset / clean / checkout）。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = _REPO_ROOT / "reports" / "u6_border_collie"
S0_DIR = OUT_DIR / "s0"

#: 按任务阶段给已跟踪改动归类，便于人工判断"若要提交该切哪一块"。
CHANGE_GROUPS: dict[str, list[str]] = {
    "U5.5 V2.1 默认接入与 136 类映射": [
        "backend/app/config.py",
        "backend/app/main.py",
        "backend/app/schemas.py",
        "backend/app/services/predictor.py",
        "frontend/src/utils/breedNames.js",
        "frontend/tests/breedNames.test.js",
        "frontend/tests/historyView.test.js",
        "tests/test_api.py",
        "tests/test_predictor_service.py",
        "启动后端.bat",
        "启动系统.bat",
    ],
    "U5/U5.2 四类候选组": [
        "backend/app/routes/predict.py",
        "frontend/src/components/PredictionResult.vue",
        "ml/predict.py",
        "ml/predictor.py",
    ],
    "U4 V2.1 训练扩展": [
        "ml/train.py",
        "tests/test_train_extensions.py",
    ],
}


def run_git(*args: str) -> str:
    """执行只读 git 命令并返回 stdout（去掉行尾空白）。"""
    result = subprocess.run(
        ["git", *args],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return f"<git {' '.join(args)} failed: {result.stderr.strip()}>"
    return result.stdout.rstrip()


def main() -> int:
    S0_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    head = run_git("log", "--oneline", "-1")
    head_sha = run_git("rev-parse", "HEAD")
    status_short = run_git("status", "--short")
    diff_stat = run_git("diff", "--stat")
    diff_check = run_git("diff", "--check")
    diff_full = run_git("diff")

    (S0_DIR / "git_head.txt").write_text(f"{head}\n{head_sha}\n",
                                         encoding="utf-8")
    (S0_DIR / "git_status_short.txt").write_text(status_short, encoding="utf-8")
    (S0_DIR / "git_diff_stat.txt").write_text(diff_stat, encoding="utf-8")
    (S0_DIR / "git_diff_check.txt").write_text(diff_check or "(无空白问题)",
                                               encoding="utf-8")
    (S0_DIR / "git_diff.txt").write_text(diff_full, encoding="utf-8")

    tracked: list[str] = []
    untracked: list[str] = []
    for line in status_short.splitlines():
        if not line.strip():
            continue
        code, _, path = line[:2], line[2:3], line[3:]
        (untracked if code.strip() == "??" else tracked).append(path.strip())

    (S0_DIR / "tracked_changes.txt").write_text("\n".join(tracked),
                                                encoding="utf-8")
    (S0_DIR / "untracked_files.txt").write_text("\n".join(untracked),
                                                encoding="utf-8")

    # ---- 归类 ----
    assigned: dict[str, str] = {}
    for group, files in CHANGE_GROUPS.items():
        for path in files:
            assigned[path] = group
    unclassified = [p for p in tracked if p not in assigned]

    # ---- V2.1 / V1.1 哈希（只读）----
    import hashlib

    def sha256(path: Path) -> str:
        if not path.exists():
            return "<missing>"
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()

    art = _REPO_ROOT / "artifacts"
    v21 = art / "v2_1_136classes_seed42"
    hashes = {
        "artifacts/best_model.pth": sha256(art / "best_model.pth"),
        "artifacts/class_names.json": sha256(art / "class_names.json"),
        "artifacts/v2_1_136classes_seed42/best_model.pth":
            sha256(v21 / "best_model.pth"),
        "artifacts/v2_1_136classes_seed42/class_names.json":
            sha256(v21 / "class_names.json"),
        "artifacts/v2_1_136classes_seed42/model_version.json":
            sha256(v21 / "model_version.json"),
        "artifacts/v2_1_136classes_seed42/experiment_config.json":
            sha256(v21 / "experiment_config.json"),
    }
    (S0_DIR / "weight_hashes.json").write_text(
        json.dumps(hashes, indent=2, ensure_ascii=False), encoding="utf-8")

    lines: list[str] = []
    add = lines.append
    add("# S0：U5.5 轻量安全固化记录（未提交）")
    add("")
    add(f"> 生成时间：{datetime.now(timezone.utc).isoformat()}")
    add("> 执行脚本：`scripts/u6_collect_s0.py`（**只读 git，无任何写操作**）")
    add("")
    add("## 1. 结论：本轮**未执行 Git 提交**")
    add("")
    add("按计划 §2.2 的退路执行：工作区同时混有 **U5.2 / U5.3 / U5.4 / U5.5** 四轮")
    add("未提交改动与大量历史产物，**无法在不误伤的前提下切分出\"仅 U5.5 接入所需\"**")
    add("的最小提交集。强行提交会把无关改动混入或漏掉运行依赖，风险高于收益。")
    add("")
    add("因此本阶段只做**可恢复与可追溯**：保存完整快照、差异清单与权重哈希，")
    add("并在此记录阻塞点，随后直接进入 U6-A（不因提交整理阻塞边牧诊断）。")
    add("")
    add("## 2. 当前 Git 状态")
    add("")
    add(f"- HEAD：`{head}`")
    add(f"- HEAD SHA：`{head_sha}`")
    add(f"- 已跟踪改动文件数：**{len(tracked)}**")
    add(f"- 未跟踪项数：**{len(untracked)}**")
    add(f"- `git diff --check`：{'无空白/冲突标记问题' if not diff_check else '见 s0/git_diff_check.txt'}")
    add("")
    add("### 2.1 已跟踪改动（按阶段归类）")
    add("")
    add("| 阶段 | 文件 |")
    add("|---|---|")
    for group, files in CHANGE_GROUPS.items():
        present = [f for f in files if f in tracked]
        if present:
            add(f"| {group} | " + "<br>".join(f"`{p}`" for p in present) + " |")
    if unclassified:
        add("| 未归类 | " + "<br>".join(f"`{p}`" for p in unclassified) + " |")
    add("")
    add("### 2.2 未跟踪项（节选，完整见 `s0/untracked_files.txt`）")
    add("")
    for path in untracked[:40]:
        add(f"- `{path}`")
    if len(untracked) > 40:
        add(f"- …其余 {len(untracked) - 40} 项见文件")
    add("")
    add("## 3. 权重与配置哈希（只读核验）")
    add("")
    add("| 文件 | SHA256 |")
    add("|---|---|")
    for path, digest in hashes.items():
        add(f"| `{path}` | `{digest}` |")
    add("")
    add("V1.1 `artifacts/best_model.pth` 期望值 "
        "`89ef468f199c6d1550fec2638c5ea6f8ef7ad543e57f8ec82c4263c121b1a256`；")
    add("本次实测" + ("**一致**。" if hashes["artifacts/best_model.pth"].startswith(
        "89ef468f199c6d1550fec2638c5ea6f8ef7ad543e57f8ec82c4263c121b1a256")
        else "**不一致，需立即停止核查**。"))
    add("")
    add("## 4. 若要提交，人工切分建议")
    add("")
    add("1. 先确认 U5.5 接入所依赖的最小集合（建议：第 2.1 节第 1 组的 11 个文件，")
    add("   加上未跟踪的 `backend/app/services/candidate_group.py`、")
    add("   `frontend/tests/predictionResult*.test.js`、`tests/test_candidate_group.py`、")
    add("   `scripts/run_four_breed_backend.py` 等运行/测试依赖）。")
    add("2. 逐文件 `git diff` 审阅，确认没有把 U5.1/U5.2 的实验脚本混入。")
    add("3. `git add <显式文件列表>`（**不要 `git add .`**），随后")
    add("   `git diff --cached --name-status` 二次核对。")
    add("4. 排除项：`artifacts/v2_1_136classes_seed42/`、`artifacts/_v2_1_smoke/`、")
    add("   任何 `reports/` 目录、`data/`、`uploads/`、`.cache/`、`*.pth`。")
    add("5. 本轮**不执行上述步骤**，留待人工决定。")
    add("")
    add("## 5. 未处理的工作区项")
    add("")
    add(f"- {len(tracked)} 个已跟踪改动、{len(untracked)} 个未跟踪项**全部原样保留**。")
    add("- 未执行 `git add` / `git commit` / `git reset --hard` / `git clean` / "
        "大范围 `checkout`。")
    add("- 未删除任何报告、数据目录或权重文件。")
    add("")
    add("## 6. 附件清单")
    add("")
    for name in sorted(p.name for p in S0_DIR.iterdir() if p.is_file()):
        add(f"- `s0/{name}`")
    add("")

    (OUT_DIR / "s0_u5_5_solidification.md").write_text("\n".join(lines),
                                                       encoding="utf-8")

    print(f"[s0] HEAD = {head}")
    print(f"[s0] tracked changes = {len(tracked)}, untracked = {len(untracked)}")
    print(f"[s0] diff --check: {'clean' if not diff_check else 'issues'}")
    print(f"[s0] V1.1 sha256 = {hashes['artifacts/best_model.pth']}")
    print(f"[s0] wrote {OUT_DIR / 's0_u5_5_solidification.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
