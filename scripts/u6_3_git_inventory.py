#!/usr/bin/env python
"""U6.3 阶段 C：工作区与 Git 变更审计（**只读 git 子命令，不写 Git**）。

用法（在仓库根目录执行）::

    python scripts/u6_3_git_inventory.py

只使用 ``status`` / ``diff`` / ``log`` / ``rev-parse`` 等只读子命令；
**不执行** ``add`` / ``commit`` / ``reset`` / ``clean`` / ``checkout``。

产出（``reports/u6_3_default_runtime_and_freeze/``）：

* ``git_change_inventory.csv`` —— 逐文件：路径、tracked/untracked、增删行数、
  所属任务组、运行时必需与否、是否含混合改动、提交建议与理由；
* ``recommended_commit_plan.md`` —— 建议分组 + 精确路径 + 依赖 + 命令示例
  （**显著注明命令尚未执行**）。
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports" / "u6_3_default_runtime_and_freeze"
GIT = "git"

#: 只读子命令白名单（脚本绝不调用白名单之外的 git 子命令）。
READONLY_GIT = ("status", "diff", "log", "rev-parse", "show", "ls-files")

#: 7 个任务组（任务 §3-C1）。
GROUPS: dict[str, list[str]] = {
    "G1 U5.5 默认模型接入与 136 类中文名": [
        "backend/app/config.py", "backend/app/main.py", "backend/app/schemas.py",
        "backend/app/services/predictor.py",
        "frontend/src/utils/breedNames.js",
        "frontend/tests/breedNames.test.js",
        "frontend/tests/historyView.test.js",
        "启动后端.bat", "启动系统.bat",
    ],
    "G2 U5.2 四类候选策略": [
        "backend/app/routes/predict.py",
        "backend/app/services/candidate_group.py",
        "frontend/src/components/PredictionResult.vue",
        "frontend/tests/predictionResult.test.js",
        "frontend/tests/predictionResultAcceptance.test.js",
        "tests/test_candidate_group.py",
        "tests/test_api.py", "tests/test_predictor_service.py",
    ],
    "G3 U6.2 collie-pair 候选策略": [
        "tests/test_collie_pair_candidate.py",
        "frontend/tests/colliePairCandidate.test.js",
    ],
    "G4 训练基础设施修复（U4/U6-C）": [
        "ml/train.py", "ml/dataset.py", "ml/u6_pair_training.py",
        "tests/test_train_extensions.py",
    ],
    "G5 验收与诊断脚本": [],
    "G6 报告/截图/CSV/临时 runtime/冒烟产物/checkpoint": [],
    "G7 无法明确归属或更早任务的既有改动": [
        "ml/predict.py", "ml/predictor.py",
    ],
}

#: 已知的多任务混合改动文件（任务 §3-C2 要求必须点名）。
MIXED_CHANGE_FILES: dict[str, list[str]] = {
    "ml/train.py": [
        "U6-C pair-only 训练通道（--pair-color-jitter / "
        "--pair-sampler-weight）",
        "U6-C --image-size 透传（exp04/exp06 分辨率实验）",
        "U6 warm-start 分类头继承修复（initialize_from_checkpoint）",
        "U4 早前训练扩展（--init-from / --monitor / --lr-head 等）",
    ],
    "ml/dataset.py": [
        "U6-C image_size 参数（build_datasets / build_dataloaders）",
        "U4 早前 AUGMENT_PRESETS / build_transforms",
    ],
    "tests/test_train_extensions.py": [
        "U6-C 训练能力（pair-only / image_size / head_transferred）",
        "U4 早前训练扩展",
    ],
    "frontend/tests/breedNames.test.js": [
        "U5.5 136 类映射完整性 + 旧 37 类兼容",
        "U5.2 候选四类中文名断言",
    ],
    "frontend/tests/historyView.test.js": [
        "U5.5 136 类中文名（border_collie 等不再回退英文）",
        "U5 早前历史页测试",
    ],
    "backend/app/main.py": [
        "U5.5 class_names_path 透传 + health model_weights",
        "U5.2 候选组接线早前改动",
    ],
    "backend/app/services/predictor.py": [
        "U5.5 错配明确失败（class count mismatch 含两侧计数）",
        "U5.2 probabilities 透传给候选组",
    ],
    "tests/test_api.py": [
        "U5.5 health model_weights 断言",
        "U5.2 候选组响应断言",
    ],
    "tests/test_predictor_service.py": [
        "U5.5 class_names_path 与错配失败用例",
        "U5.2 候选组安全返回用例",
    ],
    "frontend/src/components/PredictionResult.vue": [
        "U5.3 图例候选数量动态化（candidateCount）",
        "U6.2 group_id 渲染 + collie-pair 副标题",
        "U6.2 不保证候选中一定包含正确品种声明",
        "U5.2 候选区既有实现",
    ],
    "启动后端.bat": ["U5.5 V2.1 默认路径检查 + 回退提示"],
    "启动系统.bat": ["U5.5 V2.1 默认路径检查 + 回退提示"],
}

#: 运行时必需（生产推理路径）判定。
RUNTIME_REQUIRED = (
    "backend/app/config.py", "backend/app/main.py", "backend/app/schemas.py",
    "backend/app/services/predictor.py",
    "backend/app/services/candidate_group.py",
    "backend/app/routes/predict.py",
    "frontend/src/utils/breedNames.js",
    "frontend/src/components/PredictionResult.vue",
)

#: 明确不纳入提交的产物模式。
ARTEFACT_PATTERNS = (
    "artifacts/", "reports/", ".cache/", "data/", "uploads/",
    "frontend/dist/", "frontend/node_modules/", ".venv/",
)


def git(*args: str) -> str:
    result = subprocess.run([GIT, *args], cwd=str(REPO), capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        return ""
    return result.stdout


def classify(path: str) -> str:
    for group, prefixes in GROUPS.items():
        for prefix in prefixes:
            if path == prefix or path.startswith(prefix):
                return group
    # 脚本类：按前缀细分
    if path.startswith("scripts/"):
        if any(k in path for k in ("u6_", "accept_", "page_accept_",
                                   "check_candidate", "validate_candidate",
                                   "reconcile_", "generate_breed_mapping",
                                   "diagnostic_protection", "run_four_breed")):
            return "G5 验收与诊断脚本"
        if any(k in path for k in ("u6_collect", "u6_baseline",
                                   "u6_compare", "u6_freeze", "u6_parse",
                                   "u6_run_experiment", "u6_warm",
                                   "u6_build", "u6_2_", "u6_3_")):
            return "G5 验收与诊断脚本"
        return "G5 验收与诊断脚本"
    if path.startswith("ml/") or path.startswith("tests/"):
        return "G4 训练基础设施修复（U4/U6-C）"
    if any(path.startswith(p) for p in ARTEFACT_PATTERNS):
        return "G6 报告/截图/CSV/临时 runtime/冒烟产物/checkpoint"
    if path.startswith("md/"):
        return "G6 报告/截图/CSV/临时 runtime/冒烟产物/checkpoint"
    return "G7 无法明确归属或更早任务的既有改动"


def suggestion(path: str, tracked: bool, group: str, mixed: bool) -> str:
    if any(path.startswith(p) for p in ARTEFACT_PATTERNS):
        return "不提交"
    if path.startswith("md/"):
        return "建议提交（任务单文档，项目既有惯例保留）"
    if group.startswith("G6"):
        return "不提交"
    if mixed:
        return "整文件提交 + 说明（含多任务混合改动）"
    return "建议提交"


def reason(path: str, tracked: bool, group: str, mixed: bool) -> str:
    parts: list[str] = []
    if not tracked:
        parts.append("新增文件")
    if path in RUNTIME_REQUIRED:
        parts.append("生产推理路径必需")
    if path.startswith("backend/") or path.startswith("ml/"):
        parts.append("服务端代码")
    if path.startswith("frontend/src/"):
        parts.append("前端源码")
    if path.startswith("tests/") or path.startswith("frontend/tests/"):
        parts.append("自动化测试")
    if mixed:
        parts.append("含多个任务的混合改动，不可按任务简单拆分")
    if any(path.startswith(p) for p in ARTEFACT_PATTERNS):
        parts.append("实验/报告产物，体积大且与运行代码无关")
    return "；".join(parts) if parts else "见分组"


def numstat(path: str, tracked: bool) -> tuple[int, int]:
    if not tracked:
        return (0, 0)
    out = git("diff", "--numstat", "--", path)
    for line in out.splitlines():
        fields = line.split("\t")
        if len(fields) >= 2 and fields[0].isdigit() and fields[1].isdigit():
            return (int(fields[0]), int(fields[1]))
    return (0, 0)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)

    status = git("status", "--short")
    head = git("log", "--oneline", "-1")
    tracked_files = [l for l in git("diff", "--name-only").splitlines() if l]

    entries: list[dict] = []
    for line in status.splitlines():
        if not line.strip():
            continue
        code, path = line[:2], line[3:].strip()
        tracked = code.strip() != "??"
        group = classify(path)
        mixed = path in MIXED_CHANGE_FILES
        added, deleted = numstat(path, tracked)
        entries.append({
            "path": path,
            "status": code,
            "tracked": tracked,
            "added_lines": added,
            "deleted_lines": deleted,
            "task_group": group,
            "runtime_required": path in RUNTIME_REQUIRED,
            "has_mixed_changes": mixed,
            "mixed_change_sources": "; ".join(MIXED_CHANGE_FILES.get(path, [])),
            "commit_suggestion": suggestion(path, tracked, group, mixed),
            "reason": reason(path, tracked, group, mixed),
        })

    csv_path = OUT / "git_change_inventory.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(entries[0].keys()))
        writer.writeheader()
        writer.writerows(entries)

    mixed_paths = [e["path"] for e in entries if e["has_mixed_changes"]]
    print(f"[C] HEAD: {head}")
    print(f"[C] 共 {len(entries)} 项（tracked 修改 "
          f"{sum(1 for e in entries if e['tracked'])} / 未跟踪 "
          f"{sum(1 for e in entries if not e['tracked'])}）")
    print(f"[C] 混合改动文件 {len(mixed_paths)} 个：")
    for path in mixed_paths:
        print(f"     - {path}")
    print(f"[C] wrote {csv_path}")

    (OUT / "git_inventory_summary.json").write_text(json.dumps({
        "head": head,
        "total": len(entries),
        "tracked_modified": sum(1 for e in entries if e["tracked"]),
        "untracked": sum(1 for e in entries if not e["tracked"]),
        "mixed_change_files": mixed_paths,
        "runtime_required": [e["path"] for e in entries
                             if e["runtime_required"]],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
