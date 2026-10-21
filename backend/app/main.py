"""FastAPI application entry point.

Run from the repository root:

    python -m uvicorn backend.app.main:app --reload --port 8000

The model is loaded exactly once during the application lifespan and reused
for every request. If loading fails, the app still starts (so /api/health
can report the problem) but /api/predict answers 503 instead of returning
fabricated results.
"""
from __future__ import annotations

import logging
import re
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Allow running from any working directory.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from .config import Settings  # noqa: E402
from .database import init_db  # noqa: E402
from .routes import api_router  # noqa: E402
from .schemas import HealthResponse  # noqa: E402
from .services.predictor import PredictorService  # noqa: E402

logger = logging.getLogger("uvicorn.error")


def _safe_model_error(exc: Exception) -> str:
    """Short, path-free reason for why the model is not ready."""
    if isinstance(exc, FileNotFoundError):
        return "model weights file is missing"
    message = str(exc)
    # 权重与类别表错配是**配置错误**，必须在健康状态里直接说清楚是两侧类别数
    # 不一致（不暴露服务器绝对路径），而不是笼统的 "failed to load"。
    if "class count mismatch" in message:
        match = re.search(r"\((\d+) classes\),.*?\((\d+) classes\)",
                          message, re.S)
        if match:
            return (
                f"class mapping mismatch: checkpoint has {match.group(1)} "
                f"classes but class_names.json has {match.group(2)}. "
                f"Point CATDOG_WEIGHTS_PATH and CATDOG_CLASS_NAMES_PATH at a "
                f"matching pair.")
    return f"model failed to load ({type(exc).__name__})"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    app.state.session_factory = init_db(settings.db_path)
    logger.info("database ready: %s", settings.db_path.name)

    if getattr(app.state, "predictor_injected", False):
        # Tests inject a fake predictor; keep it untouched.
        logger.info("using injected predictor (test mode)")
    else:
        try:
            app.state.predictor = PredictorService(
                weights_path=settings.weights_path, device=settings.device,
                class_names_path=settings.class_names_path,
                candidate_group_enabled=settings.candidate_group_enabled)
            app.state.model_error = None
        except Exception as exc:
            # Log the full reason server-side, expose only a short reason.
            logger.exception("model loading failed")
            app.state.predictor = None
            app.state.model_error = _safe_model_error(exc)
    yield
    app.state.predictor = None


def create_app(settings: Settings | None = None,
               predictor=None) -> FastAPI:
    """Application factory.

    ``predictor`` may be injected (tests use a lightweight fake); when it is
    not injected the real model is loaded during the lifespan.
    """
    app = FastAPI(
        title=settings.app_name if settings else "CatDogBreedNet API",
        version=settings.version if settings else "1.0.0",
        description=("Cat/dog breed classification API. Upload an image to "
                     "get the most likely breed with Top-K scores."),
        lifespan=lifespan,
    )
    app.state.settings = settings or Settings.from_env()
    app.state.predictor = predictor
    app.state.predictor_injected = predictor is not None
    app.state.model_error = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app.state.settings.cors_origins,
        allow_credentials=False,   # never combine credentials with a wildcard
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code,
                            content={"success": False, "error": exc.detail})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("unhandled error on %s %s", request.method,
                         request.url.path)
        return JSONResponse(status_code=500,
                            content={"success": False,
                                     "error": "internal server error"})

    @app.get("/api/health", response_model=HealthResponse, tags=["health"])
    async def health(request: Request) -> HealthResponse:
        """Service and model readiness. No paths or internals are exposed."""
        predictor = request.app.state.predictor
        weights = getattr(predictor, "weights_path", None)
        return HealthResponse(
            status="ok",
            model_loaded=predictor is not None,
            num_classes=(predictor.num_classes if predictor else None),
            model_weights=(Path(weights).name if weights else None),
            model_error=request.app.state.model_error,
            version=request.app.state.settings.version,
            time=datetime.now(timezone.utc).isoformat(),
        )

    return app


app = create_app()
