"""Backend configuration.

Every value can be overridden through environment variables (see
``.env.example``); defaults are safe for local development and resolve all
paths from the repository root, so no machine-specific absolute path is
hard-coded (CODEBUDDY.md rule 7). No path defaults to the C: drive.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# backend/app/config.py -> <repo root> is two levels up
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ml.config import ARTIFACTS_DIR, ROOT_DIR  # noqa: E402

#: 默认推理模型目录（V2.1，136 类）。权重与类别映射必须取自同一目录，
#: 否则 ``PredictorService`` 会因类别数不匹配而在启动阶段明确失败。
#: V1.1（37 类）的文件仍保留在 ``ARTIFACTS_DIR`` 根目录，未做任何改动，
#: 需要回退时用环境变量指向它们即可（见 reports/u5_5_v2_1_integration/rollback.md）。
DEFAULT_MODEL_DIR = ARTIFACTS_DIR / "v2_1_136classes_seed42"

ENV_PREFIX = "CATDOG_"


def _env(name: str, default: str) -> str:
    return os.environ.get(f"{ENV_PREFIX}{name}", default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    """Parse an explicit boolean flag; anything else falls back to default."""
    raw = _env(name, "1" if default else "0").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = _env(name, ",".join(default))
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the backend application."""

    app_name: str = "CatDogBreedNet API"
    version: str = "1.0.0"

    # --- model ---
    #: 权重与类别映射必须**配对**使用：index i 的输出必须对应同一品种。
    #: 两者类别数不一致时，``PredictorService`` 会在启动阶段明确失败，
    #: 绝不静默降级或改用其他类别表。
    #: U5.5 起默认模型为 V2.1（136 类）；V1.1 的 37 类文件仍在原路径未改动，
    #: 需要时用 ``CATDOG_WEIGHTS_PATH`` / ``CATDOG_CLASS_NAMES_PATH`` 回退。
    weights_path: Path = DEFAULT_MODEL_DIR / "best_model.pth"
    #: 与 ``weights_path`` 配对的类别映射文件（可独立配置，见
    #: ``CATDOG_CLASS_NAMES_PATH``）。
    class_names_path: Path = DEFAULT_MODEL_DIR / "class_names.json"
    device: str = "auto"               # auto | cpu | cuda
    default_top_k: int = 3

    # --- 相近犬种候选组（四类 B1：APBT / AmStaff / SBT / American Bulldog）---
    # U5.5 起随 V2.1 一起默认**开启**（该能力已在 U5.2/U5.3/U5.4 验收）。
    # 阈值与版本号未变：mass >= 0.30、margin <= 0.40、
    # threshold_version = "val-2026-10-19-four-breed-b1"。
    # 该开关只影响"是否附加候选组展示信息"，不改变模型、权重、类别定义；
    # 需要关闭时设置 CATDOG_CANDIDATE_GROUP_ENABLED=false。
    candidate_group_enabled: bool = True

    # --- uploads & validation ---
    upload_dir: Path = ROOT_DIR / "uploads"
    max_upload_bytes: int = 10 * 1024 * 1024      # 10 MB
    max_image_pixels: int = 25_000_000            # 25 MP
    allowed_formats: tuple[str, ...] = ("JPEG", "PNG", "WEBP")

    # --- database ---
    db_path: Path = ROOT_DIR / "data" / "app.db"

    # --- CORS (development origins only by default) ---
    cors_origins: list[str] = field(
        default_factory=lambda: ["http://localhost:5173",
                                 "http://127.0.0.1:5173"])

    # --- history & stats ---
    history_default_page_size: int = 20
    history_max_page_size: int = 100
    stats_top_breeds: int = 10
    stats_trend_days: int = 14

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from CATDOG_* environment variables."""
        formats = tuple(
            fmt.strip().upper()
            for fmt in _env_list("ALLOWED_FORMATS", ["JPEG", "PNG", "WEBP"]))
        return cls(
            weights_path=Path(_env(
                "WEIGHTS_PATH", str(DEFAULT_MODEL_DIR / "best_model.pth"))),
            class_names_path=Path(_env(
                "CLASS_NAMES_PATH", str(DEFAULT_MODEL_DIR / "class_names.json"))),
            device=_env("DEVICE", "auto"),
            default_top_k=_env_int("DEFAULT_TOP_K", 3),
            candidate_group_enabled=_env_bool("CANDIDATE_GROUP_ENABLED", True),
            upload_dir=Path(_env("UPLOAD_DIR", str(ROOT_DIR / "uploads"))),
            max_upload_bytes=_env_int("MAX_UPLOAD_MB", 10) * 1024 * 1024,
            max_image_pixels=_env_int("MAX_IMAGE_PIXELS", 25_000_000),
            allowed_formats=formats or ("JPEG", "PNG", "WEBP"),
            db_path=Path(_env("DB_PATH", str(ROOT_DIR / "data" / "app.db"))),
            cors_origins=_env_list(
                "CORS_ORIGINS",
                ["http://localhost:5173", "http://127.0.0.1:5173"]),
            history_default_page_size=_env_int("HISTORY_PAGE_SIZE", 20),
            history_max_page_size=_env_int("HISTORY_MAX_PAGE_SIZE", 100),
            stats_top_breeds=_env_int("STATS_TOP_BREEDS", 10),
            stats_trend_days=_env_int("STATS_TREND_DAYS", 14),
        )

    @property
    def upload_dir_resolved(self) -> Path:
        return self.upload_dir.resolve()
