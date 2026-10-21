"""API tests for the FastAPI backend.

These tests inject a lightweight fake Predictor and use temporary SQLite
databases / upload directories, so pytest never downloads weights and never
runs real deep-learning inference (CODEBUDDY.md section 10.2).
"""
import io
import json
import sys
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.exc import SQLAlchemyError

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.config import Settings  # noqa: E402
from backend.app.database import get_db  # noqa: E402
from backend.app.main import create_app  # noqa: E402
from backend.app.models import PredictionRecord, utc_now_iso  # noqa: E402
from backend.app.services.image_utils import (  # noqa: E402
    ImageValidationError,
    UploadTooLarge,
    delete_upload,
    read_upload_with_limit,
    save_upload,
    validate_image,
)

FAKE_CLASSES = [f"fake_breed_{i:02d}" for i in range(37)]


class FakeUpload:
    """Minimal async file-like object for read_upload_with_limit tests."""

    def __init__(self, data: bytes, chunk_size: int = 64 * 1024):
        self._stream = io.BytesIO(data)
        self._chunk_size = chunk_size

    async def read(self, size: int = -1):
        if size is None or size < 0:
            return self._stream.read()
        return self._stream.read(min(size, self._chunk_size))


class FakePredictor:
    """Deterministic stand-in for the real PredictorService."""

    def __init__(self, class_names=None, fail: bool = False):
        self.class_names = list(class_names or FAKE_CLASSES)
        self.num_classes = len(self.class_names)
        self.fail = fail
        #: 与真实 PredictorService 对齐：健康接口会回报实际加载的权重文件名。
        self.weights_path = Path("fake.pth")

    def predict_pil(self, image, top_k: int = 3):
        if self.fail:
            raise RuntimeError("inference failure")
        if not 1 <= top_k <= self.num_classes:
            raise ValueError("top_k out of range")
        # Deterministic "prediction" derived from the image content.
        grey = image.convert("L")
        mean_value = sum(grey.getdata()) / max(1, grey.size[0] * grey.size[1])
        top_index = int(mean_value) % self.num_classes
        predictions = []
        remaining = 1.0
        for rank in range(top_k):
            idx = (top_index + rank) % self.num_classes
            score = 0.9 if rank == 0 else remaining / (top_k - rank)
            remaining -= score
            predictions.append({"breed": self.class_names[idx],
                                "confidence": round(score, 6)})
        return {"predictions": predictions, "inference_ms": 1.5,
                "preprocess_ms": 0.2}


def make_jpeg_bytes(size=(300, 200), color=(120, 80, 40)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="JPEG")
    return buffer.getvalue()


def make_bmp_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (10, 20, 30)).save(buffer, format="BMP")
    return buffer.getvalue()


def make_settings(tmp_path: Path, **overrides) -> Settings:
    values = dict(
        upload_dir=tmp_path / "uploads",
        db_path=tmp_path / "app.db",
        weights_path=tmp_path / "missing.pth",
        cors_origins=["http://localhost:5173"],
        max_upload_bytes=10 * 1024 * 1024,
        max_image_pixels=25_000_000,
    )
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def client_with_fake(tmp_path):
    """App with an injected fake predictor and a temporary SQLite DB."""
    settings = make_settings(tmp_path)
    app = create_app(settings=settings, predictor=FakePredictor())
    with TestClient(app) as client:
        yield client, app, settings


@pytest.fixture
def client_without_model(tmp_path):
    """App whose lifespan fails to load the (missing) weights."""
    settings = make_settings(tmp_path)
    app = create_app(settings=settings)  # no injection -> real load attempt
    with TestClient(app) as client:
        yield client, app, settings


def seed_records(session_factory, count: int, upload_dir: Path) -> list[int]:
    """Insert prediction records directly; returns their ids."""
    upload_dir.mkdir(parents=True, exist_ok=True)
    session = session_factory()
    ids = []
    for i in range(count):
        image = upload_dir / f"seed_{i:03d}.jpg"
        image.write_bytes(b"not-a-real-image")
        record = PredictionRecord(
            image_path=str(image),
            predicted_breed=f"fake_breed_{i % 3:02d}",
            confidence=0.5 + i / 1000,
            top_k_json=json.dumps(
                [{"breed": f"fake_breed_{i % 3:02d}", "confidence": 0.5}]),
            inference_ms=10.0 + i,
            created_at=f"2026-10-13T10:00:{i:02d}+00:00",
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        ids.append(record.id)
    session.close()
    return ids


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------

def test_health_ok_with_model(client_with_fake):
    client, _, _ = client_with_fake
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert body["num_classes"] == 37
    assert body["model_error"] is None
    assert body["time"].endswith("+00:00")  # UTC ISO 8601


def test_health_model_not_ready(client_without_model):
    client, _, _ = client_without_model
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["model_loaded"] is False
    assert body["model_error"]
    # 模型未就绪时不应报出权重文件名
    assert body.get("model_weights") is None
    # no absolute paths or stack traces leak into the health payload
    assert "\\" not in json.dumps(body) and "Traceback" not in json.dumps(body)


def test_health_reports_loaded_weights_name(client_with_fake):
    """U5.5：健康接口必须能证明"实际加载了哪个权重"，而非只凭配置宣称。"""
    client, _, _ = client_with_fake
    body = client.get("/api/health").json()
    assert body["model_weights"] == "fake.pth"
    # 只暴露文件名，不泄露服务器绝对路径
    assert "\\" not in body["model_weights"]
    assert "/" not in body["model_weights"]


def test_health_response_model_weights_is_optional():
    """旧版响应（无 model_weights 字段）必须仍能通过 schema 校验。"""
    from backend.app.schemas import HealthResponse

    legacy = HealthResponse(
        status="ok", model_loaded=True, num_classes=37, model_error=None,
        version="1.0.0", time="2026-10-19T00:00:00+00:00")
    assert legacy.model_weights is None
    assert legacy.model_dump()["num_classes"] == 37


def test_predict_returns_503_when_model_not_ready(client_without_model):
    client, _, _ = client_without_model
    response = client.post(
        "/api/predict",
        files={"file": ("pet.jpg", make_jpeg_bytes(), "image/jpeg")},
        data={"top_k": "3"},
    )
    assert response.status_code == 503
    assert "not ready" in response.json()["error"]


# ---------------------------------------------------------------------------
# predict - happy path and structure
# ---------------------------------------------------------------------------

def test_predict_valid_jpeg_structure_and_persistence(client_with_fake):
    client, app, settings = client_with_fake
    response = client.post(
        "/api/predict",
        files={"file": ("pet.jpg", make_jpeg_bytes(), "image/jpeg")},
        data={"top_k": "3"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert isinstance(body["record_id"], int) and body["record_id"] > 0
    assert len(body["predictions"]) == 3
    assert body["top_k"] == 3 and body["num_classes"] == 37
    for item in body["predictions"]:
        assert item["breed"].startswith("fake_breed_")
        assert 0.0 <= item["confidence"] <= 1.0
    assert body["elapsed_ms"] > 0
    assert body["inference_ms"] > 0
    assert body["preprocess_ms"] > 0
    assert "softmax" in body["note"]

    # the record really is in the database
    session = app.state.session_factory()
    record = session.get(PredictionRecord, body["record_id"])
    assert record is not None
    assert record.predicted_breed == body["predictions"][0]["breed"]
    assert json.loads(record.top_k_json)[0]["breed"] == record.predicted_breed
    assert record.created_at.endswith("+00:00")  # UTC ISO 8601
    session.close()
    # and the uploaded image was stored with a random name
    saved = Path(record.image_path)
    assert saved.is_file()
    assert saved.parent == settings.upload_dir_resolved
    assert saved.name != "pet.jpg"


def test_predict_top_k_one(client_with_fake):
    client, _, _ = client_with_fake
    response = client.post(
        "/api/predict",
        files={"file": ("pet.jpg", make_jpeg_bytes(), "image/jpeg")},
        data={"top_k": "1"},
    )
    assert response.status_code == 200
    assert len(response.json()["predictions"]) == 1


@pytest.mark.parametrize("bad_top_k", ["0", "-1", "38", "99"])
def test_predict_top_k_out_of_range(client_with_fake, bad_top_k):
    client, _, _ = client_with_fake
    response = client.post(
        "/api/predict",
        files={"file": ("pet.jpg", make_jpeg_bytes(), "image/jpeg")},
        data={"top_k": bad_top_k},
    )
    assert response.status_code == 400
    assert "top_k" in response.json()["error"]


# ---------------------------------------------------------------------------
# predict - upload validation
# ---------------------------------------------------------------------------

def test_predict_empty_file(client_with_fake):
    client, _, settings = client_with_fake
    response = client.post(
        "/api/predict",
        files={"file": ("empty.jpg", b"", "image/jpeg")},
        data={"top_k": "3"},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["error"]
    assert not any(settings.upload_dir_resolved.glob("*"))


def test_predict_text_disguised_as_jpeg(client_with_fake):
    client, _, _ = client_with_fake
    response = client.post(
        "/api/predict",
        files={"file": ("fake.jpg", b"this is definitely not an image",
                        "image/jpeg")},
        data={"top_k": "3"},
    )
    assert response.status_code == 400
    assert "decode" in response.json()["error"]


def test_predict_corrupt_jpeg(client_with_fake):
    client, _, _ = client_with_fake
    valid = make_jpeg_bytes()
    truncated = valid[: len(valid) // 2]
    response = client.post(
        "/api/predict",
        files={"file": ("broken.jpg", truncated, "image/jpeg")},
        data={"top_k": "3"},
    )
    assert response.status_code == 400


def test_predict_unsupported_format(client_with_fake):
    client, _, _ = client_with_fake
    response = client.post(
        "/api/predict",
        files={"file": ("image.bmp", make_bmp_bytes(), "image/bmp")},
        data={"top_k": "3"},
    )
    assert response.status_code == 400
    assert "unsupported" in response.json()["error"]


def test_predict_file_too_large(tmp_path):
    settings = make_settings(tmp_path, max_upload_bytes=2048)
    app = create_app(settings=settings, predictor=FakePredictor())
    with TestClient(app) as client:
        response = client.post(
            "/api/predict",
            files={"file": ("big.jpg", make_jpeg_bytes(size=(800, 800)),
                            "image/jpeg")},
            data={"top_k": "3"},
        )
    assert response.status_code == 413
    assert "limit" in response.json()["error"]


def test_predict_too_many_pixels(tmp_path):
    settings = make_settings(tmp_path, max_image_pixels=1000)
    app = create_app(settings=settings, predictor=FakePredictor())
    with TestClient(app) as client:
        response = client.post(
            "/api/predict",
            files={"file": ("huge.jpg", make_jpeg_bytes(size=(64, 64)),
                            "image/jpeg")},
            data={"top_k": "3"},
        )
    assert response.status_code == 400
    assert "pixels" in response.json()["error"]


# ---------------------------------------------------------------------------
# predict - failure paths
# ---------------------------------------------------------------------------

def test_predict_inference_failure_cleans_orphan_upload(tmp_path):
    settings = make_settings(tmp_path)
    app = create_app(settings=settings, predictor=FakePredictor(fail=True))
    with TestClient(app) as client:
        response = client.post(
            "/api/predict",
            files={"file": ("pet.jpg", make_jpeg_bytes(), "image/jpeg")},
            data={"top_k": "3"},
        )
    assert response.status_code == 500
    # the uploaded image must not linger without a database record
    assert not any(settings.upload_dir_resolved.glob("*"))


def test_predict_database_failure_cleans_orphan_upload(tmp_path):
    settings = make_settings(tmp_path)
    app = create_app(settings=settings, predictor=FakePredictor())

    class FailingSession:
        def add(self, obj):
            pass

        def commit(self):
            raise SQLAlchemyError("commit failed")

        def rollback(self):
            pass

        def refresh(self, obj):
            pass

        def close(self):
            pass

    def failing_get_db(request: Request):
        session = FailingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = failing_get_db
    with TestClient(app) as client:
        response = client.post(
            "/api/predict",
            files={"file": ("pet.jpg", make_jpeg_bytes(), "image/jpeg")},
            data={"top_k": "3"},
        )
    assert response.status_code == 500
    body = response.json()
    assert body["success"] is False
    # no absolute paths / stack traces in client-facing errors
    assert str(tmp_path) not in response.text
    assert "Traceback" not in response.text
    # orphan upload cleaned up
    assert not any(settings.upload_dir_resolved.glob("*"))


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------

def test_history_pagination_and_order(client_with_fake):
    client, app, settings = client_with_fake
    seed_records(app.state.session_factory, 25, settings.upload_dir_resolved)

    page1 = client.get("/api/history?page=1&page_size=10").json()
    assert page1["total"] == 25
    assert len(page1["items"]) == 10
    timestamps = [item["created_at"] for item in page1["items"]]
    assert timestamps == sorted(timestamps, reverse=True)  # newest first

    page3 = client.get("/api/history?page=3&page_size=10").json()
    assert len(page3["items"]) == 5
    assert page3["items"][0]["id"] not in [i["id"] for i in page1["items"]]


def test_history_detail_found_and_missing(client_with_fake):
    client, app, settings = client_with_fake
    (record_id,) = seed_records(app.state.session_factory, 1,
                                settings.upload_dir_resolved)
    found = client.get(f"/api/history/{record_id}")
    assert found.status_code == 200
    item = found.json()["item"]
    assert item["id"] == record_id
    assert item["image_filename"].startswith("seed_")
    assert "\\" not in item["image_filename"] and "/" not in item["image_filename"]

    missing = client.get("/api/history/999999")
    assert missing.status_code == 404


def test_history_delete_removes_record_and_image(client_with_fake):
    client, app, settings = client_with_fake
    (record_id,) = seed_records(app.state.session_factory, 1,
                                settings.upload_dir_resolved)
    session = app.state.session_factory()
    image_path = Path(session.get(PredictionRecord, record_id).image_path)
    session.close()
    assert image_path.is_file()

    response = client.delete(f"/api/history/{record_id}")
    assert response.status_code == 200
    assert response.json()["deleted_id"] == record_id
    assert response.json()["image_deleted"] is True
    assert not image_path.exists()

    session = app.state.session_factory()
    assert session.get(PredictionRecord, record_id) is None
    session.close()
    assert client.get(f"/api/history/{record_id}").status_code == 404


def test_history_delete_never_touches_files_outside_upload_dir(client_with_fake,
                                                               tmp_path):
    client, app, settings = client_with_fake
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"keep-me")
    session = app.state.session_factory()
    record = PredictionRecord(
        image_path=str(outside),
        predicted_breed="fake_breed_00",
        confidence=0.9,
        top_k_json=json.dumps([{"breed": "fake_breed_00",
                                "confidence": 0.9}]),
        inference_ms=1.0,
        created_at=utc_now_iso(),
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    record_id = record.id
    session.close()

    response = client.delete(f"/api/history/{record_id}")
    assert response.status_code == 200
    assert response.json()["image_deleted"] is False
    assert outside.is_file()  # file outside the upload dir is untouched


def test_history_delete_missing_record(client_with_fake):
    client, _, _ = client_with_fake
    assert client.delete("/api/history/424242").status_code == 404


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_empty_database(client_with_fake):
    client, _, _ = client_with_fake
    body = client.get("/api/stats").json()
    assert body["success"] is True
    assert body["total_predictions"] == 0
    assert body["breed_distribution"] == []
    assert body["daily_trend"] == []
    assert body["avg_inference_ms"] is None


def test_stats_from_real_records(client_with_fake):
    client, app, settings = client_with_fake
    seed_records(app.state.session_factory, 5, settings.upload_dir_resolved)
    body = client.get("/api/stats").json()
    assert body["total_predictions"] == 5
    distribution = {row["breed"]: row["count"]
                    for row in body["breed_distribution"]}
    assert distribution["fake_breed_00"] == 2  # i % 3 == 0 for i in 0,3
    assert distribution["fake_breed_01"] == 2
    assert distribution["fake_breed_02"] == 1
    counts = [row["count"] for row in body["breed_distribution"]]
    assert counts == sorted(counts, reverse=True)
    expected_avg = sum(10.0 + i for i in range(5)) / 5
    assert body["avg_inference_ms"] == pytest.approx(expected_avg, abs=0.01)
    assert body["daily_trend"] == [
        {"date": "2026-10-13", "count": 5}]


# ---------------------------------------------------------------------------
# image_utils unit tests
# ---------------------------------------------------------------------------

def test_validate_image_roundtrip_and_random_names(tmp_path):
    settings = make_settings(tmp_path)
    data = make_jpeg_bytes()
    image, image_format = validate_image(data, settings)
    assert image_format == "JPEG"
    assert image.mode == "RGB"

    names = set()
    for _ in range(5):
        path, _ = save_upload(data, settings)
        assert path.is_file()
        assert path.parent == settings.upload_dir_resolved
        names.add(path.name)
    assert len(names) == 5  # random names, no user input involved


def test_delete_upload_rejects_outside_path(tmp_path):
    settings = make_settings(tmp_path)
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"x")
    assert delete_upload(outside, settings) is False
    assert outside.is_file()
    inside = settings.upload_dir_resolved
    inside.mkdir(parents=True, exist_ok=True)
    target = inside / "inside.jpg"
    target.write_bytes(b"x")
    assert delete_upload(target, settings) is True
    assert not target.exists()


def test_read_upload_with_limit_raises():
    data = b"x" * (300 * 1024)
    with pytest.raises(UploadTooLarge):
        import asyncio

        asyncio.run(read_upload_with_limit(FakeUpload(data), 100 * 1024))


def test_read_upload_with_limit_ok():
    import asyncio

    data = b"x" * (50 * 1024)
    result = asyncio.run(read_upload_with_limit(FakeUpload(data),
                                                100 * 1024))
    assert result == data


def test_validate_image_rejects_unsupported_and_empty(tmp_path):
    settings = make_settings(tmp_path)
    with pytest.raises(ImageValidationError, match="empty"):
        validate_image(b"", settings)
    with pytest.raises(ImageValidationError, match="unsupported"):
        validate_image(make_bmp_bytes(), settings)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

def test_cors_allows_configured_origin(client_with_fake):
    client, _, _ = client_with_fake
    response = client.get("/api/health",
                          headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == \
        "http://localhost:5173"


def test_cors_rejects_unknown_origin(client_with_fake):
    client, _, _ = client_with_fake
    response = client.get("/api/health",
                          headers={"Origin": "http://evil.example.com"})
    assert "access-control-allow-origin" not in response.headers
