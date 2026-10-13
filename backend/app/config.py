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

ENV_PREFIX = "CATDOG_"


def _env(name: str, default: str) -> str:
    return os.environ.get(f"{ENV_PREFIX}{name}", default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
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
    weights_path: Path = ARTIFACTS_DIR / "best_model.pth"
    device: str = "auto"               # auto | cpu | cuda
    default_top_k: int = 3

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
            weights_path=Path(_env("WEIGHTS_PATH",
                                   str(ARTIFACTS_DIR / "best_model.pth"))),
            device=_env("DEVICE", "auto"),
            default_top_k=_env_int("DEFAULT_TOP_K", 3),
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
