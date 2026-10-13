"""Pydantic response schemas for the backend API."""
from __future__ import annotations

from pydantic import BaseModel, Field

SCORE_NOTE = ("confidence is a softmax score over the trained class set, "
              "not a true probability")


class PredictionItem(BaseModel):
    """One Top-K entry."""

    breed: str = Field(..., description="predicted breed name")
    confidence: float = Field(..., ge=0.0, le=1.0,
                              description="softmax score over trained classes")


class PredictResponse(BaseModel):
    """Response of POST /api/predict."""

    success: bool = True
    record_id: int
    predictions: list[PredictionItem]
    elapsed_ms: float = Field(
        ..., description="server-side processing time: image validation, "
                         "preprocessing and inference combined")
    inference_ms: float = Field(
        ..., description="model forward pass only (excludes preprocessing)")
    preprocess_ms: float = Field(
        ..., description="image decode/transform time (excludes inference)")
    top_k: int
    num_classes: int
    note: str = SCORE_NOTE


class HistoryItem(BaseModel):
    """One history record (server paths are never exposed)."""

    id: int
    image_filename: str = Field(
        ..., description="server-side file name only, never a full path")
    predicted_breed: str
    confidence: float
    predictions: list[PredictionItem]
    inference_ms: float
    created_at: str = Field(
        ..., description="UTC ISO 8601 timestamp, e.g. 2026-10-13T10:00:00+00:00")


class HistoryListResponse(BaseModel):
    """Response of GET /api/history."""

    success: bool = True
    total: int
    page: int
    page_size: int
    items: list[HistoryItem]


class HistoryDetailResponse(BaseModel):
    """Response of GET /api/history/{record_id}."""

    success: bool = True
    item: HistoryItem


class HistoryDeleteResponse(BaseModel):
    """Response of DELETE /api/history/{record_id}."""

    success: bool = True
    deleted_id: int
    image_deleted: bool = Field(
        ..., description="whether the uploaded image file was removed")


class BreedCount(BaseModel):
    breed: str
    count: int


class DailyCount(BaseModel):
    date: str = Field(..., description="UTC calendar day, YYYY-MM-DD")
    count: int


class StatsResponse(BaseModel):
    """Response of GET /api/stats; every number comes from real records."""

    success: bool = True
    total_predictions: int
    breed_distribution: list[BreedCount]
    daily_trend: list[DailyCount]
    avg_inference_ms: float | None


class HealthResponse(BaseModel):
    """Response of GET /api/health."""

    status: str
    model_loaded: bool
    num_classes: int | None = None
    model_error: str | None = Field(
        None, description="short reason when the model is not ready")
    version: str
    time: str = Field(..., description="current server time, UTC ISO 8601")
