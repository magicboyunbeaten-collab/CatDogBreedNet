#!/usr/bin/env python
"""U6.4.1：登记**有意排除**的剩余未跟踪项（只读）。

用法（在仓库根目录执行）::

    python scripts/u6_4_1_remaining_inventory.py \
        --out reports/u6_4_1_git_finalization/remaining_worktree_inventory.csv

设计原则
--------
* 只读：仅调用 ``git status`` / ``git ls-files``，不做任何写操作。
* **不删除、不隐藏、不改 .gitignore**：本脚本的输出用于证明"这些是刻意留下的
  本地审计/实验资料"，而不是为了把 ``git status`` 弄干净。
* 对目录型条目统计其下文件数与总字节，让读者知道排除了多少体积。
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: 前缀 -> (类型, 是否运行时必需, 排除理由)
RULES: list[tuple[str, str, str, str]] = [
    ("artifacts/", "model_weights_and_experiments", "no",
     "V1.1/V2.1/V2.2 权重与训练产物；.pth 体积达数十 MB，任务明确禁止入库"),
    ("reports/", "acceptance_reports_and_runtime", "no",
     "验收报告/CSV/截图/临时 SQLite 与 uploads 副本；项目历史从未跟踪 reports/，"
     "延续既有惯例（并非内容无价值）"),
    ("data/", "dataset", "no", "训练/验证/测试图片与标签；禁止入库"),
    ("uploads/", "runtime_uploads", "no", "正式上传目录；禁止入库"),
    (".cache/", "cache_and_scratch", "no", "临时日志、冒烟产物、Playwright 安装等缓存"),
    ("frontend/dist/", "build_output", "no", "前端构建产物，可由 npm run build 重新生成"),
    ("frontend/node_modules/", "dependencies", "no", "第三方依赖，由 package.json 决定"),
    (".venv/", "virtualenv", "no", "Python 虚拟环境"),
    ("scripts/", "one_off_scripts", "no",
     "一次性验收/诊断/实验脚本，尚未证明为长期维护工具；U6.4 审核结论为继续单独"
     "审核、不批量提交（其中 4 个还含机器本地绝对路径）"),
    ("md/", "task_sheets", "no",
     "任务单文档；有追溯价值，但项目未将 md/ 纳入版本控制，是否入库待人工决定"),
]


def git(*args: str) -> str:
    result = subprocess.run(["git", "-c", "core.quotepath=false", *args],
                            cwd=str(REPO), capture_output=True)
    return result.stdout.decode("utf-8", errors="surrogateescape")


def dir_stats(path: str) -> tuple[int, int]:
    target = REPO / path
    if not target.is_dir():
        if target.is_file():
            return 1, target.stat().st_size
        return 0, 0
    files = 0
    size = 0
    for item in target.rglob("*"):
        if item.is_file():
            files += 1
            try:
                size += item.stat().st_size
            except OSError:
                pass
    return files, size


def classify(path: str) -> tuple[str, str, str]:
    for prefix, kind, required, reason in RULES:
        if path.startswith(prefix):
            return kind, required, reason
    return "other", "no", "不在 A/B/C/D 精确提交清单中，且未匹配已知类型；保持原样待人工判断"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    untracked = [l.strip() for l in
                 git("ls-files", "--others", "--exclude-standard").splitlines()
                 if l.strip()]

    rows: list[dict] = []
    for path in untracked:
        kind, required, reason = classify(path)
        files, size = dir_stats(path)
        rows.append({
            "path": path,
            "type": kind,
            "runtime_required": required,
            "file_count": files,
            "total_bytes": size,
            "reason_excluded": reason,
            "intentional": "yes",
        })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys())
                                if rows else ["path"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"[inventory] 剩余未跟踪项：{len(rows)} 条")
    by_type: dict[str, list[dict]] = {}
    for row in rows:
        by_type.setdefault(row["type"], []).append(row)
    for kind, items in sorted(by_type.items()):
        total_files = sum(i["file_count"] for i in items)
        total_bytes = sum(i["total_bytes"] for i in items)
        print(f"  {kind:<32} {len(items):>3} 条 / {total_files:>6} 文件 / "
              f"{total_bytes / 1e6:.1f} MB")
    print(f"[inventory] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
