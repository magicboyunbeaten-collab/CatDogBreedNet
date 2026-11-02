#!/usr/bin/env python
"""U5.3 隔离验收用后端启动器（**不修改任何生产配置默认值**）。

用法（在仓库根目录执行）::

    # 候选组开启（四类 B1）
    python scripts/run_four_breed_backend.py --enable-candidate-group

    # 候选组关闭（复测"恢复原行为"）
    python scripts/run_four_breed_backend.py --disable-candidate-group

为什么需要这个启动器
--------------------
``PredictorService`` 在构造时会用默认 ``class_names_path``
（``ml.model.CLASS_NAMES_PATH`` → ``artifacts/class_names.json``，**37 类**）
校验 checkpoint 的类别映射。若直接把 ``CATDOG_WEIGHTS_PATH`` 指向 136 类的
V2.1 权重，校验会因 class count mismatch 失败，``/api/predict`` 返回 503。

``backend/app/main.py`` 的 lifespan 只透传 ``weights_path`` / ``device`` /
``candidate_group_enabled``，不开放 ``class_names_path``。因此本脚本**自行
构造** ``Settings`` 与 ``PredictorService``（``class_names_path`` 指向 V2.1 的
136 类映射），再交给 ``create_app(settings=..., predictor=...)``。

隔离边界
--------
* SQLite → ``--runtime-dir/app.db``（与 ``data/app.db`` 物理隔离）
* 上传   → ``--runtime-dir/uploads/``（与项目 ``uploads/`` 物理隔离）
* 权重/类别映射 → **只读** V2.1 目录，不写入

**不修改** ``backend/app/config.py``、``backend/app/main.py``、``ml/config.py``
的任何默认值；正式部署路径完全不变。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

V2_1_DIR = _REPO_ROOT / "artifacts" / "v2_1_136classes_seed42"
DEFAULT_RUNTIME = (_REPO_ROOT / "reports" / "v2_1_four_breed_page_acceptance"
                   / "runtime")


def build_isolated_app(runtime_dir: Path, enable_candidate_group: bool):
    """构造隔离 app：临时 DB/uploads + V2.1 权重 + V2.1 的 136 类映射。"""
    from backend.app.config import Settings
    from backend.app.main import create_app
    from backend.app.services.predictor import PredictorService

    weights = V2_1_DIR / "best_model.pth"
    class_names = V2_1_DIR / "class_names.json"
    for path in (weights, class_names):
        if not path.exists():
            raise FileNotFoundError(f"missing required file: {path}")

    runtime_dir.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        weights_path=weights,
        device="auto",
        upload_dir=runtime_dir / "uploads",
        db_path=runtime_dir / "app.db",
        cors_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        max_upload_bytes=10 * 1024 * 1024,
        max_image_pixels=25_000_000,
        candidate_group_enabled=enable_candidate_group,
    )
    service = PredictorService(
        weights_path=settings.weights_path,
        device=settings.device,
        class_names_path=class_names,          # 关键：136 类映射
        candidate_group_enabled=enable_candidate_group,
    )
    print(f"[launcher] weights      = {weights}")
    print(f"[launcher] class_names  = {class_names}")
    print(f"[launcher] num_classes  = {service.num_classes}")
    print(f"[launcher] candidate_group_enabled = {enable_candidate_group}")
    print(f"[launcher] db_path      = {settings.db_path}")
    print(f"[launcher] upload_dir   = {settings.upload_dir}")
    return create_app(settings=settings, predictor=service)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--enable-candidate-group", action="store_true",
                       help="开启四类候选组（本次页面验收主场景）")
    group.add_argument("--disable-candidate-group", action="store_true",
                       help="关闭候选组，用于验证恢复原有行为")
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME,
                        help="临时 DB/uploads 目录（默认报告目录下 runtime/）")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    app = build_isolated_app(args.runtime_dir,
                             enable_candidate_group=args.enable_candidate_group)

    import uvicorn
    print(f"[launcher] serving on http://{args.host}:{args.port}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
