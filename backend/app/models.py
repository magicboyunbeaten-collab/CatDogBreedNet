"""SQLAlchemy ORM models.

Timestamps are stored as UTC ISO 8601 strings with an explicit ``+00:00``
offset (e.g. ``2026-10-13T10:00:00.123456+00:00``) so the stored value is
unambiguous and still sorts lexicographically.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now_iso() -> str:
    """Current UTC time as an ISO 8601 string with explicit offset."""
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class PredictionRecord(Base):
    """One stored prediction (no user system in the MVP)."""

    __tablename__ = "prediction_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True,
                                    autoincrement=True)
    image_path: Mapped[str] = mapped_column(String(512), nullable=False)
    predicted_breed: Mapped[str] = mapped_column(String(128), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    top_k_json: Mapped[str] = mapped_column(Text, nullable=False)
    inference_ms: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False,
                                            default=utc_now_iso)
