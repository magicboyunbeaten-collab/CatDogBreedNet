"""API routers."""
from fastapi import APIRouter

from . import history, predict, stats

api_router = APIRouter()
api_router.include_router(predict.router)
api_router.include_router(history.router)
api_router.include_router(stats.router)
