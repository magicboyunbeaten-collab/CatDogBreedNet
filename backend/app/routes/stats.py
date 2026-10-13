"""GET /api/stats - statistics computed from real database records."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PredictionRecord
from ..schemas import BreedCount, DailyCount, StatsResponse

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats", response_model=StatsResponse)
def get_stats(request: Request,
              db: Session = Depends(get_db)) -> StatsResponse:
    """Aggregate prediction statistics from the database.

    Empty database -> zero counts and empty lists (never hard-coded demo
    data). ``avg_inference_ms`` is null when there are no records.
    """
    settings = request.app.state.settings

    total = db.scalar(select(func.count()).select_from(PredictionRecord)) or 0
    if total == 0:
        return StatsResponse(success=True, total_predictions=0,
                             breed_distribution=[], daily_trend=[],
                             avg_inference_ms=None)

    breed_stmt = (
        select(PredictionRecord.predicted_breed,
               func.count(PredictionRecord.id).label("count"))
        .group_by(PredictionRecord.predicted_breed)
        .order_by(func.count(PredictionRecord.id).desc())
        .limit(settings.stats_top_breeds)
    )
    breed_distribution = [
        BreedCount(breed=breed, count=count)
        for breed, count in db.execute(breed_stmt).all()
    ]

    # created_at is stored as UTC ISO 8601, so the day prefix is the UTC day.
    day = func.substr(PredictionRecord.created_at, 1, 10)
    trend_stmt = (
        select(day.label("day"), func.count(PredictionRecord.id).label("count"))
        .group_by(day)
        .order_by(day.desc())
        .limit(settings.stats_trend_days)
    )
    trend_rows = db.execute(trend_stmt).all()
    daily_trend = [DailyCount(date=row_day, count=count)
                   for row_day, count in reversed(trend_rows)]

    avg_inference = db.scalar(
        select(func.avg(PredictionRecord.inference_ms)))

    return StatsResponse(
        success=True,
        total_predictions=total,
        breed_distribution=breed_distribution,
        daily_trend=daily_trend,
        avg_inference_ms=(round(float(avg_inference), 3)
                          if avg_inference is not None else None),
    )
