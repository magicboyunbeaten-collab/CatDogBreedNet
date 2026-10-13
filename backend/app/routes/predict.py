"""POST /api/predict - upload an image and get breed predictions."""
from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PredictionRecord, utc_now_iso
from ..schemas import PredictResponse
from ..services.image_utils import (
    ImageValidationError,
    UploadTooLarge,
    delete_upload,
    read_upload_with_limit,
    save_upload,
)

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/api", tags=["predict"])


@router.post("/predict", response_model=PredictResponse)
async def predict(
    request: Request,
    file: UploadFile = File(..., description="image file (JPEG/PNG/WebP)"),
    top_k: int = Form(3, description="number of top predictions"),
    db: Session = Depends(get_db),
) -> PredictResponse:
    """Validate the upload, run the shared model and persist the record.

    ``elapsed_ms`` covers server-side processing (validation + preprocessing
    + inference); ``inference_ms`` covers the model forward pass only.
    """
    settings = request.app.state.settings
    predictor = request.app.state.predictor
    if predictor is None:
        raise HTTPException(
            status_code=503,
            detail=("model is not ready"
                    + (f": {request.app.state.model_error}"
                       if request.app.state.model_error else "")))

    if not 1 <= top_k <= predictor.num_classes:
        raise HTTPException(
            status_code=400,
            detail=f"top_k must be between 1 and {predictor.num_classes}, "
                   f"got {top_k}")

    started = time.perf_counter()

    # --- 1. stream the upload with a hard size limit ---
    try:
        data = await read_upload_with_limit(file, settings.max_upload_bytes)
    except UploadTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    # --- 2. real decode, format whitelist, pixel limit, random-name save ---
    try:
        saved_path, image = save_upload(data, settings)
    except ImageValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # --- 3. inference through the shared, already-loaded model ---
    try:
        result = predictor.predict_pil(image, top_k=top_k)
    except Exception as exc:  # never leak internals to the client
        logger.exception("inference failed")
        delete_upload(saved_path, settings)  # avoid an orphan upload
        raise HTTPException(
            status_code=500,
            detail="prediction failed; please try again") from exc

    # --- 4. persist the record; a DB failure is not a successful predict ---
    record = PredictionRecord(
        image_path=str(saved_path),
        predicted_breed=result["predictions"][0]["breed"],
        confidence=result["predictions"][0]["confidence"],
        top_k_json=json.dumps(result["predictions"], ensure_ascii=False),
        inference_ms=result["inference_ms"],
        created_at=utc_now_iso(),
    )
    try:
        db.add(record)
        db.commit()
        db.refresh(record)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("failed to persist prediction record")
        delete_upload(saved_path, settings)  # remove the now-orphaned image
        raise HTTPException(
            status_code=500,
            detail="prediction succeeded but could not be saved to history") \
            from exc

    elapsed_ms = (time.perf_counter() - started) * 1000
    return PredictResponse(
        success=True,
        record_id=record.id,
        predictions=result["predictions"],
        elapsed_ms=round(elapsed_ms, 3),
        inference_ms=result["inference_ms"],
        preprocess_ms=result["preprocess_ms"],
        top_k=top_k,
        num_classes=predictor.num_classes,
    )
