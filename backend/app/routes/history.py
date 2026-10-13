"""History endpoints: list, detail and delete prediction records."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PredictionRecord
from ..schemas import HistoryDetailResponse, HistoryItem, HistoryListResponse, \
    HistoryDeleteResponse
from ..services.image_utils import delete_upload

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/api", tags=["history"])


def _to_item(record: PredictionRecord) -> HistoryItem:
    return HistoryItem(
        id=record.id,
        image_filename=Path(record.image_path).name,
        predicted_breed=record.predicted_breed,
        confidence=record.confidence,
        predictions=json.loads(record.top_k_json),
        inference_ms=record.inference_ms,
        created_at=record.created_at,
    )


@router.get("/history", response_model=HistoryListResponse)
def list_history(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> HistoryListResponse:
    """List prediction records, newest first, with pagination."""
    settings = request.app.state.settings
    page_size = min(page_size, settings.history_max_page_size)

    total = db.scalar(select(func.count()).select_from(PredictionRecord)) or 0
    stmt = (
        select(PredictionRecord)
        .order_by(PredictionRecord.created_at.desc(),
                  PredictionRecord.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    records = db.execute(stmt).scalars().all()
    return HistoryListResponse(
        success=True,
        total=total,
        page=page,
        page_size=page_size,
        items=[_to_item(record) for record in records],
    )


@router.get("/history/{record_id}", response_model=HistoryDetailResponse)
def get_history(record_id: int,
                db: Session = Depends(get_db)) -> HistoryDetailResponse:
    """Return one prediction record by id."""
    record = db.get(PredictionRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404,
                            detail=f"record {record_id} not found")
    return HistoryDetailResponse(success=True, item=_to_item(record))


@router.delete("/history/{record_id}", response_model=HistoryDeleteResponse)
def delete_history(record_id: int, request: Request,
                   db: Session = Depends(get_db)) -> HistoryDeleteResponse:
    """Delete a record and its uploaded image (only inside the upload dir).

    Transaction order: the database row is committed first, then the image
    file is removed best-effort. If the image removal fails the record is
    already gone (logged), which is safer than the reverse order where a
    failed commit would leave a dangling image reference.
    """
    settings = request.app.state.settings
    record = db.get(PredictionRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404,
                            detail=f"record {record_id} not found")

    image_path = record.image_path
    try:
        db.delete(record)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("failed to delete record %s", record_id)
        raise HTTPException(status_code=500,
                            detail="failed to delete record") from exc

    image_deleted = delete_upload(image_path, settings)
    if not image_deleted:
        logger.warning("record %s deleted but its image was not removed "
                       "(missing or outside the upload dir)", record_id)
    return HistoryDeleteResponse(success=True, deleted_id=record_id,
                                 image_deleted=image_deleted)
