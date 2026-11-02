#!/usr/bin/env python
"""U6.3 阶段 A1：默认启动配置的**静态**审计（只读，不修改任何文件）。

用法（在仓库根目录执行）::

    python scripts/u6_3_static_audit.py

核验并记录四层概念中的前三层（第四层 API 行为由 ``u6_3_runtime_probe.py`` 取证）：

1. ``config_defaults`` —— ``Settings()`` 的类默认值；
2. ``launcher_script_settings`` —— 两个 ``.bat`` **显式 set** 与**读取**的
   ``CATDOG_*`` 变量（实测：只读取、不设置）；
3. ``process_effective_values`` —— ``Settings.from_env()`` 的实际解析值。

同时核验 ``main.py`` 的四项透传、``resolve_candidate_group`` 的 Top-1 分发逻辑，
以及 V1.1（37 类）空间下两套候选策略的安全退回行为。

产出：``reports/u6_3_default_runtime_and_freeze/runtime_config_evidence.json``
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT_DIR = REPO / "reports" / "u6_3_default_runtime_and_freeze"

BAT_FILES = ["启动后端.bat", "启动系统.bat", "启动前端.bat"]


def scan_bat(path: Path) -> dict:
    """解析 .bat 中显式 set 与读取的 CATDOG_* 变量（只读文件内容）。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    sets = sorted(set(re.findall(r'(?im)^\s*set\s+"?(CATDOG_[A-Z_]+)', text)))
    reads = sorted(set(re.findall(r'CATDOG_[A-Z_]+', text)) - set(sets))
    model_dir = re.search(r'set\s+"MODEL_DIR=([^"]+)"', text)
    uvicorn = re.search(r'uvicorn\s+(\S+)', text)
    return {
        "file": path.name,
        "lines": len(text.splitlines()),
        "sets_catdog_vars": sets,
        "reads_catdog_vars": reads,
        "model_dir": model_dir.group(1) if model_dir else None,
        "launches_uvicorn": bool(uvicorn),
        "uvicorn_target": uvicorn.group(1) if uvicorn else None,
        "has_model_path_logic": "MODEL_DIR" in text,
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    evidence: dict = {
        "generated_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "scope": "static audit only (read-only); no file modified",
    }

    # ---- 1. 配置默认值（类默认，不经环境变量）----
    from backend.app.config import DEFAULT_MODEL_DIR, Settings

    class_defaults = Settings()
    evidence["config_defaults"] = {
        "source": "backend/app/config.py — Settings() class defaults "
                  "(no environment variables involved)",
        "default_model_dir": str(DEFAULT_MODEL_DIR),
        "weights_path": str(class_defaults.weights_path),
        "class_names_path": str(class_defaults.class_names_path),
        "candidate_group_enabled": class_defaults.candidate_group_enabled,
        "device": class_defaults.device,
    }

    # ---- 2. 启动脚本显式设置的值 ----
    evidence["launcher_script_settings"] = {
        "source": "direct read of the three .bat launchers "
                  "(regex over set / CATDOG_* tokens)",
        "scripts": [scan_bat(REPO / name) for name in BAT_FILES],
        "summary": "启动脚本不设置任何 CATDOG_* 环境变量；它们只在 "
                   "`if not defined CATDOG_*` 中读取，用于决定是否检查 "
                   "V2.1 默认路径。因此日常启动时进程有效值等于 config.py "
                   "默认值。",
    }

    # ---- 3. 进程实际读取的有效值 ----
    effective = Settings.from_env()
    evidence["process_effective_values"] = {
        "source": "Settings.from_env() evaluated in this process "
                  "(inherits the ambient environment)",
        "weights_path": str(effective.weights_path),
        "class_names_path": str(effective.class_names_path),
        "candidate_group_enabled": effective.candidate_group_enabled,
        "device": effective.device,
        "db_path": str(effective.db_path),
        "upload_dir": str(effective.upload_dir),
        "matches_config_defaults": (
            effective.weights_path == class_defaults.weights_path
            and effective.class_names_path == class_defaults.class_names_path
            and effective.candidate_group_enabled
            == class_defaults.candidate_group_enabled),
    }

    # ---- 4. 环境变量覆盖规则 ----
    evidence["env_override_rules"] = {
        "source": "backend/app/config.py — _env / _env_bool",
        "variables": {
            "CATDOG_WEIGHTS_PATH": "覆盖 weights_path",
            "CATDOG_CLASS_NAMES_PATH": "覆盖 class_names_path",
            "CATDOG_CANDIDATE_GROUP_ENABLED": "覆盖候选总开关",
            "CATDOG_DEVICE": "覆盖 device",
            "CATDOG_UPLOAD_DIR": "覆盖 upload_dir",
            "CATDOG_DB_PATH": "覆盖 db_path",
        },
        "bool_parsing": "1/true/yes/on -> True；0/false/no/off -> False；"
                        "其它值回退到默认值（当前默认 True）",
    }

    # ---- 5. main.py 透传链路 ----
    main_src = (REPO / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    evidence["main_py_plumbing"] = {
        "source": "backend/app/main.py",
        "passes_class_names_path": "class_names_path=settings.class_names_path"
                                   in main_src,
        "passes_candidate_flag": "candidate_group_enabled="
                                 "settings.candidate_group_enabled" in main_src,
        "passes_weights_path": "weights_path=settings.weights_path"
                               in main_src,
        "health_reports_model_weights": "model_weights=" in main_src,
    }

    # ---- 6. 候选分发逻辑 ----
    from backend.app.services.candidate_group import (
        CANDIDATE_GROUP,
        COLLIE_PAIR_GROUP,
        COLLIE_PAIR_MARGIN_THRESHOLD,
        COLLIE_PAIR_MASS_THRESHOLD,
        COLLIE_PAIR_VERSION,
        GROUP_ID_COLLIE_PAIR,
        GROUP_ID_FOUR_BREED,
        MARGIN_THRESHOLD,
        MASS_THRESHOLD,
        THRESHOLD_VERSION,
    )
    evidence["candidate_dispatch"] = {
        "source": "backend/app/services/candidate_group.py",
        "master_switch_semantics": "enabled=False -> resolve_candidate_group "
                                   "returns None for BOTH strategies",
        "dispatch_rule": "按原始 Top-1 分发：top1 in COLLIE_PAIR_GROUP -> "
                         "build_collie_pair_group；否则 -> "
                         "build_candidate_group（四类）",
        "four_breed_bully": {
            "group_id": GROUP_ID_FOUR_BREED,
            "members": list(CANDIDATE_GROUP),
            "mass_threshold": MASS_THRESHOLD,
            "margin_threshold": MARGIN_THRESHOLD,
            "threshold_version": THRESHOLD_VERSION,
        },
        "collie_pair": {
            "group_id": GROUP_ID_COLLIE_PAIR,
            "members": list(COLLIE_PAIR_GROUP),
            "mass_threshold": COLLIE_PAIR_MASS_THRESHOLD,
            "margin_threshold": COLLIE_PAIR_MARGIN_THRESHOLD,
            "threshold_version": COLLIE_PAIR_VERSION,
        },
        "groups_are_disjoint": not (set(CANDIDATE_GROUP)
                                    & set(COLLIE_PAIR_GROUP)),
    }

    # ---- 7. V1.1 安全退回（函数级验证，不加载权重）----
    from backend.app.services.candidate_group import (
        build_candidate_group,
        build_collie_pair_group,
    )
    v11_classes = json.loads(
        (REPO / "artifacts" / "class_names.json").read_text(encoding="utf-8"))
    pair_predictions = [
        {"breed": "collie", "confidence": 0.6032},
        {"breed": "border_collie", "confidence": 0.3955},
    ]
    bully_predictions = [
        {"breed": "american_pit_bull_terrier", "confidence": 0.42},
        {"breed": "american_staffordshire_terrier", "confidence": 0.30},
        {"breed": "staffordshire_bull_terrier", "confidence": 0.18},
        {"breed": "american_bulldog", "confidence": 0.06},
    ]
    pair_result_v11 = build_collie_pair_group(
        pair_predictions, class_names=v11_classes)
    bully_result_v11 = build_candidate_group(
        bully_predictions, class_names=v11_classes)
    evidence["v1_1_fallback_behaviour"] = {
        "source": "function-level check against artifacts/class_names.json "
                  "(37 classes); no weights loaded",
        "v11_class_count": len(v11_classes),
        "collie_pair_returns_none": pair_result_v11 is None,
        "four_breed_returns_none": bully_result_v11 is None,
        "raises": False,
        "reason": "两套策略都要求候选成员全部存在于类别空间中；V1.1 的 37 类"
                  "既不含 AmStaff，也不含 collie / border_collie，因此安全"
                  "返回 None，不抛异常、不干扰原始预测。",
    }

    (OUT_DIR / "runtime_config_evidence.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- 控制台摘要 ----
    print("[A1] 配置默认值：")
    print(f"     weights_path            = {evidence['config_defaults']['weights_path']}")
    print(f"     class_names_path        = {evidence['config_defaults']['class_names_path']}")
    print(f"     candidate_group_enabled = "
          f"{evidence['config_defaults']['candidate_group_enabled']}")
    print("[A1] 启动脚本显式设置的 CATDOG_* 变量：")
    for script in evidence["launcher_script_settings"]["scripts"]:
        print(f"     {script['file']}: set={script['sets_catdog_vars'] or '无'} "
              f"read={script['reads_catdog_vars'] or '无'}")
    print(f"[A1] 进程有效值与配置默认一致："
          f"{evidence['process_effective_values']['matches_config_defaults']}")
    print(f"[A1] main.py 透传：class_names_path="
          f"{evidence['main_py_plumbing']['passes_class_names_path']} "
          f"candidate_flag={evidence['main_py_plumbing']['passes_candidate_flag']}")
    print(f"[A1] V1.1 安全退回：collie_pair={pair_result_v11 is None} "
          f"four_breed={bully_result_v11 is None}")
    print(f"[A1] wrote {OUT_DIR / 'runtime_config_evidence.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
