from __future__ import annotations

from datetime import datetime
from pathlib import Path

from quiz_relay.config import Settings
from quiz_relay.core import IMAGE_MIME_TYPES
from quiz_relay.errors import InvalidImageError

CONTENT_TYPE_SUFFIXES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def save_upload(settings: Settings, mode: str, content_type: str, body: bytes) -> Path:
    suffix = CONTENT_TYPE_SUFFIXES.get(content_type.lower())
    if suffix is None or suffix not in IMAGE_MIME_TYPES:
        supported = ", ".join(sorted(CONTENT_TYPE_SUFFIXES))
        raise InvalidImageError(f"Unsupported Content-Type {content_type!r}. Supported: {supported}")
    if not body:
        raise InvalidImageError("Request body is empty.")
    if len(body) > settings.api_max_upload_bytes:
        raise InvalidImageError(f"Image exceeds max_upload_bytes ({settings.api_max_upload_bytes}).")

    settings.api_upload_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    safe_mode = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in mode)
    path = settings.api_upload_dir / f"{stamp}-{safe_mode}{suffix}"
    path.write_bytes(body)
    return path
