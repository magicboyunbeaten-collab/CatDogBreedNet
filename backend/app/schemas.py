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


class CandidateBreedItem(BaseModel):
    """One entry of the look-alike candidate group.

    ``group_score`` is a *within-group* relative score
    (``p_i / sum(p_j for j in group) * 100``) — **not** an overall confidence,
    a true probability, or an accuracy. ``original_confidence`` keeps the raw
    softmax value so debugging/tracing stays possible.
    """

    breed: str
    breed_zh: str
    original_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="raw softmax score over trained "
                                         "classes, unmodified")
    group_score: float = Field(
        ..., description="within-candidate-group relative score in percent "
                         "(0-100); NOT an overall confidence")


class CandidateGroupInfo(BaseModel):
    """Look-alike candidate group attached to a prediction.

    ``triggered`` is False whenever the trigger conditions are not met; the
    front end must then keep rendering the legacy result view. ``None`` means
    the feature is disabled or the model's class space does not contain the
    group at all (e.g. the 37-class V1.1 model).
    """

    triggered: bool
    #: 候选组标识，用于区分两套并行策略：
    #: ``four-breed-bully``（四类斗牛候选组）或 ``collie-pair``
    #:（柯利 / 边境牧羊犬双候选）。旧响应可能不含该字段，故默认 ``None``。
    group_id: str | None = Field(
        None, description="which candidate strategy produced this group: "
                          "'four-breed-bully' or 'collie-pair'")
    threshold_version: str
    top1_breed: str
    top1_confidence: float
    candidates: list[CandidateBreedItem]
    available_candidates: list[str]
    group_mass: float = Field(
        ..., description="sum of raw softmax scores of the available "
                         "candidates")
    group_margin: float = Field(
        ..., description="raw-score gap between the group's top-1 and top-2")
    reason: str


class PredictResponse(BaseModel):
    """Response of POST /api/predict."""

    success: bool = True
    record_id: int
    predictions: list[PredictionItem]
    candidate_group: CandidateGroupInfo | None = Field(
        None, description="look-alike candidate group; None keeps the legacy "
                          "response shape (feature disabled or not triggered)")
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
    #: 实际加载的权重文件名（仅文件名，不含服务器绝对路径）。
    #: 用于核验"日常启动入口真的加载了哪个模型"，而不是只凭配置宣称。
    #: 可选且默认 ``None``，旧响应与旧消费者不受影响。
    model_weights: str | None = Field(
        None, description="file name of the weights actually loaded "
                          "(e.g. best_model.pth); None when no model")
    #: 实际加载的**模型版本标识**（取自权重同目录的 model_version.json）。
    #: 权重文件名在 V1.1 / V2.1 / exp06 之间是相同的（都是 best_model.pth），
    #: 只有这个字段能直接说明"现在服务的是哪个模型"。
    #: 可选且默认 ``None``：模型目录没有版本文件时（或模型未就绪）保持旧行为。
    model_version: str | None = Field(
        None, description="version_id read from model_version.json next to "
                          "the loaded checkpoint; None when the metadata "
                          "file is absent")
    model_error: str | None = Field(
        None, description="short reason when the model is not ready")
    version: str
    time: str = Field(..., description="current server time, UTC ISO 8601")
