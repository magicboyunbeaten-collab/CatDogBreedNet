#!/usr/bin/env python
"""U6.4：逐文件审阅结论 → ``file_by_file_review.csv``。

用法（在仓库根目录执行）::

    python scripts/u6_4_git_review.py --out-dir reports/u6_4_git_freeze_review

设计要点
--------
* **只用只读 git 子命令**（``status`` / ``diff`` / ``rev-parse`` / ``log``）；
  脚本顶部以白名单强制约束，任何写操作子命令直接拒绝。
* **路径编码可读**：``-c core.quotepath=false`` + ``errors="surrogateescape"``，
  修复 U6.3 因 ``errors="replace"`` 导致 md 中文路径损坏成八进制转义符的缺陷。
* ``change_summary`` 来自**实际阅读 diff 的结论**（见 ``REVIEWED`` 表），
  不照抄任何既有报告的分类。
* 未逐一阅读完整 diff 的条目如实标注审阅深度，不假装已读。
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
READONLY = {"status", "diff", "rev-parse", "log", "show", "ls-files"}

#: 审阅深度：full = 已读完整 diff；summary = 已读 diff 摘要；head = 已读文件首部
DEPTH_FULL = "full-diff"
DEPTH_SUMMARY = "diff-summary"
DEPTH_HEAD = "file-head"

# ---------------------------------------------------------------------------
# 逐文件审阅结论（来自实际阅读 git diff，非继承自既有报告）
#   task_group: A=正式运行代码 B=配套测试 C=启动入口 D=训练基础设施
#               E=任务单/文档 F=暂不提交
# ---------------------------------------------------------------------------
REVIEWED: dict[str, dict] = {
    # ---------------- A 组：正式运行代码 ----------------
    "backend/app/config.py": {
        "task_group": "A", "runtime_required": True, "mixed_change": False,
        "depth": DEPTH_FULL,
        "commit_recommendation": "建议提交",
        "change_summary":
            "新增 DEFAULT_MODEL_DIR（指向 v2_1_136classes_seed42）与 _env_bool()；"
            "新增独立 class_names_path 字段；weights_path 默认翻转为 V2.1；"
            "candidate_group_enabled 默认 True。实测 git show HEAD: 确认 HEAD 版本"
            "**完全没有** class_names_path 与 candidate_group_enabled 字段，"
            "故本文件为纯新增语义，无跨任务混合。",
        "reason": "生产推理路径必需；决定默认加载哪个模型与是否附加候选组",
    },
    "backend/app/main.py": {
        "task_group": "A", "runtime_required": True, "mixed_change": True,
        "depth": DEPTH_FULL,
        "commit_recommendation": "整文件提交 + 说明",
        "change_summary":
            "三处改动：①_safe_model_error 识别 class count mismatch 并解析两侧类别数"
            "（U5.5）；②lifespan 透传 class_names_path 与 candidate_group_enabled"
            "（U5.5，但 candidate_group_enabled 透传同时服务 U5.2 接线）；"
            "③/health 新增 model_weights 字段（U5.5）。",
        "reason": "运行必需；混合 U5.5 与 U5.2，整文件提交需在 message 列明",
    },
    "backend/app/schemas.py": {
        "task_group": "A", "runtime_required": True, "mixed_change": True,
        "depth": DEPTH_SUMMARY,
        "commit_recommendation": "整文件提交 + 说明",
        "change_summary":
            "新增 CandidateBreedItem、CandidateGroupInfo（含可选 group_id）、"
            "PredictResponse.candidate_group、HealthResponse.model_weights。"
            "候选组 schema 属 U5.2/U6.2，model_weights 属 U5.5。",
        "reason": "运行必需；响应契约，候选组与 health 字段来源不同",
    },
    "backend/app/services/predictor.py": {
        "task_group": "A", "runtime_required": True, "mixed_change": True,
        "depth": DEPTH_FULL,
        "commit_recommendation": "整文件提交 + 说明",
        "change_summary":
            "①类别数错配时重抛含两侧计数与两个真实路径的错误（U5.5，且仅在数量不同时"
            "改写消息，数量相同名称不同则保留原索引级错误）；②向候选组透传完整 "
            "probabilities（U5.2/U6.2）。",
        "reason": "运行必需；错配保护与候选组概率来源分属两个任务",
    },
    "backend/app/routes/predict.py": {
        "task_group": "A", "runtime_required": True, "mixed_change": False,
        "depth": DEPTH_FULL,
        "commit_recommendation": "建议提交",
        "change_summary":
            "新增候选组计算（try/except 兜底，失败不影响原始预测）与 "
            "candidate_group 入响应；注释明确候选组绝不参与数据库写入。",
        "reason": "运行必需；纯 U5.2 候选组接线",
    },
    "backend/app/services/candidate_group.py": {
        "task_group": "A", "runtime_required": True, "mixed_change": True,
        "depth": DEPTH_FULL, "tracked_override": False,
        "commit_recommendation": "建议提交（新文件）",
        "change_summary":
            "未跟踪新文件。内含**两套并行策略**：四类 bully（group_id=four-breed-bully，"
            "mass 0.30/margin 0.40，版本 val-2026-10-19-four-breed-b1）与 collie-pair"
            "（group_id=collie-pair，mass 0.30/margin 0.30，版本 "
            "val-2026-10-21-collie-pair-v1）；resolve_candidate_group 按原始 Top-1 "
            "分发；两组均要求成员齐全否则返回 None（V1.1 安全退回）。",
        "reason": "运行必需；单文件内含两套策略，属 U5.2 与 U6.2 的叠加",
    },
    "frontend/src/utils/breedNames.js": {
        "task_group": "A", "runtime_required": True, "mixed_change": True,
        "depth": DEPTH_SUMMARY,
        "commit_recommendation": "整文件提交 + 说明",
        "change_summary":
            "BREED_NAMES_ZH 由 37 条扩到 136 条（旧 37 条原样保留），"
            "并含 CANDIDATE_GROUP / CANDIDATE_BREED_NAMES_ZH 四项候选常量。",
        "reason": "运行必需；136 类映射属 U5.5，候选四类常量属 U5.2",
    },
    "frontend/src/components/PredictionResult.vue": {
        "task_group": "A", "runtime_required": True, "mixed_change": True,
        "depth": DEPTH_SUMMARY,
        "commit_recommendation": "整文件提交 + 说明",
        "change_summary":
            "候选区渲染、candidateCount 动态数量、user-choice 独立区；"
            "U6.2 新增 group_id 可见渲染、collie-pair 专属副标题、"
            "「不保证候选中一定包含正确品种」声明；U5.3 已将硬编码「三个候选」改为动态。",
        "reason": "运行必需；叠加 U5.2/U5.3/U6.2 三轮改动",
    },
    "ml/predict.py": {
        "task_group": "A", "runtime_required": True, "mixed_change": False,
        "depth": DEPTH_FULL, "tracked_override": True,
        "commit_recommendation": "建议提交",
        "change_summary":
            "predict_from_tensor 返回值新增完整 softmax 向量 probabilities，"
            "docstring 明确「API response schema never exposes it」，"
            "目的是让候选组不把 Top-K 外候选当作 0 分。**修正 U6.3 分类："
            "U6.3 将其归入 G7『无法明确归属』，实际属候选组概率透传（U5.2/U6.2）。**",
        "reason": "运行必需；候选组得分的概率来源",
    },
    "ml/predictor.py": {
        "task_group": "A", "runtime_required": True, "mixed_change": False,
        "depth": DEPTH_FULL, "tracked_override": True,
        "commit_recommendation": "建议提交",
        "change_summary":
            "Predictor.predict_pil 透传 probabilities；docstring 说明其仅内部使用、"
            "API schema 不暴露。**同样修正 U6.3 的 G7 误分类。**",
        "reason": "运行必需；候选组概率透传链路",
    },

    # ---------------- B 组：配套测试 ----------------
    "tests/test_api.py": {
        "task_group": "B", "runtime_required": False, "mixed_change": True,
        "depth": DEPTH_SUMMARY,
        "commit_recommendation": "整文件提交 + 说明",
        "change_summary":
            "新增 health model_weights 断言与旧响应兼容用例（U5.5），"
            "以及候选组响应相关断言（U5.2）。",
        "reason": "锁定 A 组行为；跨 U5.5/U5.2",
    },
    "tests/test_predictor_service.py": {
        "task_group": "B", "runtime_required": False, "mixed_change": True,
        "depth": DEPTH_SUMMARY,
        "commit_recommendation": "整文件提交 + 说明",
        "change_summary":
            "新增 class_names_path 匹配/错配用例（U5.5，含两侧计数断言）"
            "与候选组安全返回用例（U5.2）。",
        "reason": "锁定 A 组行为；跨 U5.5/U5.2",
    },
    "frontend/tests/breedNames.test.js": {
        "task_group": "B", "runtime_required": False, "mixed_change": True,
        "depth": DEPTH_SUMMARY,
        "commit_recommendation": "整文件提交 + 说明",
        "change_summary":
            "由写死 37 条改为 136 类完整性 + 旧 37 类兼容 + 边牧/柯利/边境梗"
            "互不混淆 + 候选四类中文名断言。",
        "reason": "锁定映射行为；跨 U5.5/U5.2",
    },
    "frontend/tests/historyView.test.js": {
        "task_group": "B", "runtime_required": False, "mixed_change": True,
        "depth": DEPTH_SUMMARY,
        "commit_recommendation": "整文件提交 + 说明",
        "change_summary":
            "未映射标签回退英文的用例改用真正未知标签（因 border_collie 现已有中文名），"
            "并新增旧 37 类与新 99 类历史标签都显示中文的用例。",
        "reason": "锁定历史页兼容；跨 U5.5 与既有",
    },
    "tests/test_candidate_group.py": {
        "task_group": "B", "runtime_required": False, "mixed_change": True,
        "depth": DEPTH_FULL, "tracked_override": False,
        "commit_recommendation": "建议提交（新文件）",
        "change_summary":
            "未跟踪新文件。覆盖四类 bully 组全部触发/不触发/归一化/Top-K 外候选/"
            "不改写原始预测/V1.1 安全/开关关闭，以及 U6.2 collie-pair 的 "
            "group_id、独立阈值与版本、按 Top-1 分发。",
        "reason": "锁定两套候选策略；单文件覆盖 U5.2 与 U6.2",
    },
    "tests/test_collie_pair_candidate.py": {
        "task_group": "B", "runtime_required": False, "mixed_change": False,
        "depth": DEPTH_FULL, "tracked_override": False,
        "commit_recommendation": "建议提交（新文件）",
        "change_summary":
            "未跟踪新文件。15 个用例专测 collie-pair：触发/不触发边界、"
            "得分严格按完整概率归一化且不硬编码 50/50、Top-K 外候选不当 0、"
            "原始预测不被改写、V1.1 安全返回、开关关闭、API 不暴露概率向量、"
            "group_id 可选向后兼容。",
        "reason": "U6.2 专属回归，无跨任务混合",
    },
    "frontend/tests/predictionResult.test.js": {
        "task_group": "B", "runtime_required": False, "mixed_change": True,
        "depth": DEPTH_FULL, "tracked_override": False,
        "commit_recommendation": "建议提交（新文件）",
        "change_summary":
            "未跟踪新文件。13 个用例：四类候选渲染、图例候选数量动态化"
            "（U5.3 修复硬编码「三个候选」）、用户选择不改 Top-K、"
            "null/undefined/triggered=false 均不渲染。",
        "reason": "锁定候选区渲染；跨 U5.2/U5.3/U5.4",
    },
    "frontend/tests/predictionResultAcceptance.test.js": {
        "task_group": "B", "runtime_required": False, "mixed_change": True,
        "depth": DEPTH_HEAD, "tracked_override": False,
        "commit_recommendation": "建议提交（新文件）",
        "change_summary":
            "未跟踪新文件。依赖 reports/v2_1_four_breed_candidate_implementation/"
            "acceptance_api_responses.json（U5.3 产物）做响应回放断言。"
            "**注意：该 JSON 位于 reports/ 且未跟踪，若不入库此测试在新克隆环境下会失败。**",
        "reason": "锁定候选响应契约；但依赖未跟踪的报告产物，需人工决策",
    },
    "frontend/tests/colliePairCandidate.test.js": {
        "task_group": "B", "runtime_required": False, "mixed_change": False,
        "depth": DEPTH_FULL, "tracked_override": False,
        "commit_recommendation": "建议提交（新文件）",
        "change_summary":
            "未跟踪新文件。6 个用例专测 collie-pair 前端渲染：两候选中文名与数量、"
            "得分和约 100% 且不硬编码 50/50、文案无必然正确暗示、用户选择不改 "
            "Top-K、null/undefined/triggered=false 不渲染、按 group_id 区分两套策略。",
        "reason": "U6.2 专属前端回归，无跨任务混合",
    },

    # ---------------- C 组：启动入口 ----------------
    "启动后端.bat": {
        "task_group": "C", "runtime_required": True, "mixed_change": False,
        "depth": DEPTH_FULL,
        "commit_recommendation": "建议提交",
        "change_summary":
            "MODEL_DIR 改指 artifacts/v2_1_136classes_seed42；"
            "以 if not defined CATDOG_WEIGHTS_PATH / CATDOG_CLASS_NAMES_PATH "
            "**只读**语义决定是否检查默认路径（不设置任何 CATDOG_*）；"
            "缺失时给出可复制的 V1.1 回退提示；定义时回显已指定的环境变量。",
        "reason": "日常启动入口；纯 U5.5",
    },
    "启动系统.bat": {
        "task_group": "C", "runtime_required": True, "mixed_change": False,
        "depth": DEPTH_SUMMARY,
        "commit_recommendation": "建议提交",
        "change_summary":
            "启动前检查从 artifacts/best_model.pth 改为 V2.1 目录的两个文件，"
            "并尊重 CATDOG_* 覆盖；缺失时给出回退提示。",
        "reason": "日常启动入口；纯 U5.5",
    },

    # ---------------- D 组：训练基础设施 ----------------
    "ml/train.py": {
        "task_group": "D", "runtime_required": False, "mixed_change": True,
        "depth": DEPTH_SUMMARY,
        "commit_recommendation": "整文件提交 + 说明（独立成组，不混入生产功能提交）",
        "change_summary":
            "三类来源叠加：①U6-C pair-only 训练通道 --pair-color-jitter / "
            "--pair-sampler-weight 与 --image-size；②U6 warm-start 分类头继承修复"
            "（initialize_from_checkpoint 在类别名一致时连 fc.* 一起继承并记录 "
            "head_transferred）；③U4 早前训练扩展（--init-from/--monitor/--lr-head 等）。",
        "reason": "训练工具，与线上推理无关；含 U4/U6-C/U6 三来源，不可按任务拆分",
    },
    "ml/dataset.py": {
        "task_group": "D", "runtime_required": False, "mixed_change": True,
        "depth": DEPTH_SUMMARY,
        "commit_recommendation": "整文件提交 + 说明（独立成组）",
        "change_summary":
            "build_datasets / build_dataloaders 新增 image_size 参数（默认 224，"
            "向后兼容），供 U6-C/exp04/exp06 分辨率实验使用；"
            "其余为 U4 既有 AUGMENT_PRESETS / build_transforms。",
        "reason": "训练工具；U6-C 与 U4 混合",
    },
    "ml/u6_pair_training.py": {
        "task_group": "D", "runtime_required": False, "mixed_change": False,
        "depth": DEPTH_FULL, "tracked_override": False,
        "commit_recommendation": "建议提交（新文件）",
        "change_summary":
            "未跟踪新文件。PairColorJitterDataset（仅 collie/border_collie 施加 "
            "ColorJitter）、make_pair_weighted_sampler（仅两类加权）、parse_jitter、"
            "pair_sample_share。纯 U6-C 新增，无混合。",
        "reason": "U6-C 训练工具，无线上依赖",
    },
    "tests/test_train_extensions.py": {
        "task_group": "D", "runtime_required": False, "mixed_change": True,
        "depth": DEPTH_SUMMARY,
        "commit_recommendation": "整文件提交 + 说明（独立成组）",
        "change_summary":
            "覆盖 initialize_from_checkpoint 的 136→136 分类头继承、张量数量精确匹配、"
            "异常必须抛错（U6 warm-start 修复 + U6-C pair 能力），以及 U4 早前训练扩展。",
        "reason": "训练工具回归；U6-C/U6 与 U4 混合",
    },
}

#: 未跟踪目录/产物的默认归类（不逐一列文件）。
UNTAGGED_RULES: list[tuple[str, str, bool, bool, str, str]] = [
    # (前缀, task_group, runtime_required, mixed_change, commit_recommendation, reason)
    ("reports/", "F", False, False, "不提交",
     "报告/截图/CSV/隔离 runtime；项目历史从未跟踪 reports/，建议延续惯例"),
    ("artifacts/", "F", False, False, "不提交",
     "模型权重与实验 checkpoint；任务明确禁止把 .pth 入库"),
    ("data/", "F", False, False, "不提交", "数据集图片与标签；禁止入库"),
    ("uploads/", "F", False, False, "不提交", "正式上传目录；禁止入库"),
    (".cache/", "F", False, False, "不提交", "临时缓存与冒烟产物"),
    ("frontend/dist/", "F", False, False, "不提交", "构建产物"),
    ("frontend/node_modules/", "F", False, False, "不提交", "第三方依赖"),
    (".venv/", "F", False, False, "不提交", "虚拟环境"),
    ("md/", "E", False, False, "条件提交（需用户决定）",
     "任务单文档；有长期追溯价值，但是否入库需人工决定"),
    ("scripts/", "F", False, False, "暂不提交（一次性验收/诊断脚本）",
     "验收与诊断脚本；尚未证明为长期维护工具"),
]

#: 含机器本地绝对路径的未跟踪脚本（已扫描确认）。
LOCAL_PATH_SCRIPTS = {
    "scripts/audit_v2_data_sources.py",
    "scripts/build_clean_split.py",
    "scripts/build_v2_dataset.py",
    "scripts/diagnose_dataset.py",
}


def git(*args: str) -> str:
    if args and args[0] not in READONLY:
        raise SystemExit(f"[u6.4] 拒绝执行非只读 git 子命令：{args[0]}")
    result = subprocess.run(["git", "-c", "core.quotepath=false", *args],
                            cwd=str(REPO), capture_output=True)
    return result.stdout.decode("utf-8", errors="surrogateescape")


def numstat(path: str) -> tuple[int, int]:
    out = git("diff", "--numstat", "--", path)
    for line in out.splitlines():
        fields = line.split("\t")
        if len(fields) >= 2 and fields[0].isdigit() and fields[1].isdigit():
            return int(fields[0]), int(fields[1])
    return 0, 0


def classify_untracked(path: str) -> dict:
    for prefix, group, runtime, mixed, suggestion, reason in UNTAGGED_RULES:
        if path.startswith(prefix) or path == prefix.rstrip("/"):
            summary = "未跟踪产物/文档目录"
            if path in LOCAL_PATH_SCRIPTS:
                summary = ("一次性数据构建/诊断脚本；**含机器本地绝对路径 "
                           "E:\\CatDogBreedNet 硬编码**，提交前需先参数化")
                reason += "；且含本地绝对路径"
            return {
                "task_group": group, "runtime_required": runtime,
                "mixed_change": mixed, "commit_recommendation": suggestion,
                "change_summary": summary, "reason": reason,
                "depth": DEPTH_HEAD,
            }
    return {
        "task_group": "F", "runtime_required": False, "mixed_change": False,
        "commit_recommendation": "暂不提交", "change_summary": "未跟踪项",
        "reason": "未匹配已知规则，默认暂不提交", "depth": DEPTH_HEAD,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    status = git("status", "--short")
    entries: list[dict] = []
    for line in status.splitlines():
        if not line.strip():
            continue
        code = line[:2]
        path = line[3:].strip().strip('"')
        tracked = code.strip() != "??"
        info = REVIEWED.get(path)
        if info is None:
            info = classify_untracked(path)
        added, deleted = numstat(path) if tracked else (0, 0)
        entries.append({
            "path": path,
            "git_status": code,
            "tracked": "yes" if tracked else "no",
            "change_summary": info["change_summary"],
            "task_group": info["task_group"],
            "runtime_required": "yes" if info["runtime_required"] else "no",
            "mixed_change": "yes" if info["mixed_change"] else "no",
            "commit_recommendation": info["commit_recommendation"],
            "reason": info["reason"],
            "added_lines": added,
            "deleted_lines": deleted,
            "review_depth": info.get("depth", ""),
        })

    # 未跟踪目录（如 reports/xxx）在 status 中是一条记录，但其中可能含大量文件，
    # 这里补一行说明，避免读者误以为目录内无内容。
    fields = ["path", "git_status", "tracked", "change_summary", "task_group",
              "runtime_required", "mixed_change", "commit_recommendation",
              "reason", "added_lines", "deleted_lines", "review_depth"]
    csv_path = args.out_dir / "file_by_file_review.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields,
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(entries)

    reviewed = sum(1 for e in entries if e["path"] in REVIEWED)
    mixed = [e["path"] for e in entries if e["mixed_change"] == "yes"]
    print(f"[u6.4] 共 {len(entries)} 行；其中逐文件审阅 {reviewed} 个")
    print(f"[u6.4] 混合改动文件 {len(mixed)} 个")
    for path in mixed:
        print(f"     - {path}")
    print(f"[u6.4] wrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
