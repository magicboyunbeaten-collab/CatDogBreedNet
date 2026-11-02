#!/usr/bin/env python
"""U6.4：捕获**只读** Git 基线快照。

用法（在仓库根目录执行）::

    python scripts/u6_4_capture_baseline.py --out reports/u6_4_git_freeze_review

设计要点
--------
* **只用只读 git 子命令**：``rev-parse`` / ``status`` / ``diff`` /
  ``ls-files`` / ``log`` / ``show``。绝不调用 add/commit/reset/checkout/
  restore/clean/stash/cherry-pick/rebase。
* **路径编码可读**：用 ``-c core.quotepath=false`` 并以
  ``errors="surrogateescape"`` 解码，再以 UTF-8 写回文件——修复 U6.3
  用 ``errors="replace"`` 导致中文路径损坏成八进制转义符的缺陷。
* **先写本快照、再由调用方创建报告目录**（本脚本只写一个 txt，不含目录）。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: 只读子命令白名单——脚本只会调用这些。
READONLY = {"rev-parse", "status", "diff", "ls-files", "log", "show"}


def git(*args: str) -> str:
    """运行只读 git 命令；任何写操作子命令都会在调用前被拒绝。"""
    if args and args[0] not in READONLY:
        raise SystemExit(f"[u6.4] 拒绝执行非只读 git 子命令：{args[0]}")
    result = subprocess.run(["git", "-c", "core.quotepath=false", *args],
                            cwd=str(REPO), capture_output=True)
    # surrogateescape 保留原始字节，避免中文被替换成乱码
    return result.stdout.decode("utf-8", errors="surrogateescape")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    head_full = git("rev-parse", "HEAD").strip()
    head_short = head_full[:7]
    head_msg = git("log", "-n", "1", "--oneline").strip()
    branch = git("rev-parse", "--abbrev-ref", "HEAD").strip()
    status = git("status", "--short")
    diff_stat = git("diff", "--stat")
    diff_name_status = git("diff", "--name-status")
    cached_stat = git("diff", "--cached", "--stat")
    cached_name_status = git("diff", "--cached", "--name-status")
    untracked_raw = git("ls-files", "--others", "--exclude-standard")

    lines: list[str] = []
    add = lines.append
    add("# U6.4 只读 Git 基线快照（working_tree_before）")
    add("")
    add(f"- 捕获时间：{datetime.now(timezone.utc).isoformat()}")
    add("- 捕获方式：`scripts/u6_4_capture_baseline.py`，**仅只读 git 子命令**")
    add("")
    add("## 1. HEAD 与分支")
    add("")
    add(f"- 完整 SHA：`{head_full}`")
    add(f"- 短 SHA：`{head_short}`")
    add(f"- commit：`{head_msg}`")
    add(f"- 分支：`{branch}`")
    add("")
    add("## 2. 已暂存差异（必须为空）")
    add("")
    add("```")
    add(cached_stat.rstrip() or "(空 —— 索引无变化)")
    add("```")
    add("")
    add("## 3. `git diff --cached --name-status`")
    add("")
    add("```")
    add(cached_name_status.rstrip() or "(空)")
    add("```")
    add("")
    add("## 4. `git status --short` 全文")
    add("")
    add("```")
    add(status.rstrip())
    add("```")
    add("")

    tracked = [l for l in status.splitlines() if l.startswith(" M")]
    untracked = [l[3:].strip().strip('"') for l in status.splitlines()
                 if l.startswith("??")]
    add("## 5. 统计")
    add("")
    add(f"- 已跟踪文件被修改（` M`）：**{len(tracked)}**")
    add(f"- 未跟踪项（`??`）：**{len(untracked)}**")
    add(f"- 合计：**{len(tracked) + len(untracked)}**")
    add(f"- 未跟踪项按顶层目录："
        + ", ".join(f"{name}={count}" for name, count in sorted(
            _top_counts(untracked).items(), key=lambda kv: (-kv[1], kv[0]))))
    add("")
    add("## 6. `git diff --stat` 全文（未暂存）")
    add("")
    add("```")
    add(diff_stat.rstrip() or "(空)")
    add("```")
    add("")
    add("## 7. `git diff --name-status` 全文（未暂存）")
    add("")
    add("```")
    add(diff_name_status.rstrip() or "(空)")
    add("```")
    add("")
    add("## 8. 未跟踪文件清单（去引号、可读路径）")
    add("")
    for path in untracked:
        add(f"- `{path}`")
    add("")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")

    print(f"[u6.4] HEAD = {head_short} ({head_msg})")
    print(f"[u6.4] 分支 = {branch}")
    print(f"[u6.4] tracked M = {len(tracked)}, untracked = {len(untracked)}, "
          f"total = {len(tracked) + len(untracked)}")
    print(f"[u6.4] 已暂存差异 = {'空' if not cached_stat.strip() else '非空(异常)'}")
    print(f"[u6.4] wrote {args.out}")
    return 0


def _top_counts(paths: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in paths:
        top = path.split("/", 1)[0] if "/" in path else path
        counts[top] = counts.get(top, 0) + 1
    return counts


if __name__ == "__main__":
    raise SystemExit(main())
