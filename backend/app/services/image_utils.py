"""Upload validation and safe file handling.

Security rules implemented here (CODEBUDDY.md section 7.2):
    * stream the upload and enforce the size limit while reading;
    * really decode the image with Pillow (never trust extension/MIME);
    * whitelist formats (JPEG/PNG/WebP) and reject oversized pixel counts
      (also guards against Pillow decompression-bomb warnings/errors);
    * store files under random names inside the configured upload dir only;
    * never delete anything outside the configured upload dir.
"""
from __future__ import annotations

import io
import uuid
from pathlib import Path

from fastapi import UploadFile
from PIL import Image

from ..config import Settings

_CHUNK_SIZE = 64 * 1024

_FORMAT_EXTENSIONS = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}


class UploadTooLarge(Exception):
    """Raised when an upload exceeds the configured size limit."""

    def __init__(self, max_bytes: int):
        self.max_bytes = max_bytes
        super().__init__(
            f"file exceeds the {max_bytes / (1024 * 1024):.1f} MB limit")


class ImageValidationError(Exception):
    """Raised when the uploaded bytes are not an acceptable image."""


async def read_upload_with_limit(upload: UploadFile,
                                 max_bytes: int) -> bytes:
    """Stream an upload into memory, enforcing ``max_bytes`` while reading."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise UploadTooLarge(max_bytes)
        chunks.append(chunk)
    return b"".join(chunks)


def validate_image(data: bytes, settings: Settings) -> tuple[Image.Image, str]:
    """Validate uploaded bytes and return ``(rgb_image, format)``.

    Raises ``ImageValidationError`` for empty, unsupported, corrupt or
    oversized-pixel images. Decompression-bomb warnings/errors are handled
    by the explicit pixel check plus Pillow's own guard.
    """
    if not data:
        raise ImageValidationError("uploaded file is empty")

    try:
        with Image.open(io.BytesIO(data)) as probe:
            image_format = (probe.format or "").upper()
            if image_format not in settings.allowed_formats:
                raise ImageValidationError(
                    f"unsupported image format '{image_format or 'unknown'}'; "
                    f"allowed formats: {', '.join(settings.allowed_formats)}")
            width, height = probe.size
            if width * height > settings.max_image_pixels:
                raise ImageValidationError(
                    f"image has {width}x{height} pixels "
                    f"({width * height:,}); the limit is "
                    f"{settings.max_image_pixels:,} pixels")
            # Force a full decode so truncated / corrupt files are rejected
            # before anything is stored or predicted.
            probe.load()
    except ImageValidationError:
        raise
    except Image.DecompressionBombError as exc:
        raise ImageValidationError(
            f"image rejected by the decompression-bomb guard ({exc})") from exc
    except Exception as exc:  # UnidentifiedImageError, OSError(truncated), ...
        raise ImageValidationError(
            f"cannot decode image ({type(exc).__name__}); the file may be "
            f"corrupt or not a real image") from exc

    image = Image.open(io.BytesIO(data)).convert("RGB")
    return image, image_format


def _random_filename(image_format: str) -> str:
    extension = _FORMAT_EXTENSIONS.get(image_format, ".bin")
    return f"{uuid.uuid4().hex}{extension}"


def save_upload(data: bytes, settings: Settings) -> tuple[Path, Image.Image]:
    """Validate and store an upload under a random name.

    Returns ``(saved_path, rgb_image)``. The saved path is guaranteed to be
    inside the configured upload directory.
    """
    image, image_format = validate_image(data, settings)
    upload_dir = settings.upload_dir_resolved
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_path = (upload_dir / _random_filename(image_format)).resolve()
    if not saved_path.is_relative_to(upload_dir):
        # Defensive: uuid names can never escape the directory, but never
        # trust path construction without checking.
        raise ImageValidationError("refusing to store outside the upload dir")
    saved_path.write_bytes(data)
    return saved_path, image


def delete_upload(path: Path, settings: Settings) -> bool:
    """Delete an uploaded file, refusing anything outside the upload dir.

    Returns True when a file was actually removed.
    """
    if not path:
        return False
    try:
        target = Path(path).resolve()
    except OSError:
        return False
    upload_dir = settings.upload_dir_resolved
    if not target.is_relative_to(upload_dir):
        return False
    if target.is_file():
        target.unlink()
        return True
    return False
