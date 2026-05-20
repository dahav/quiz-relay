from __future__ import annotations

import hmac
import os
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Header, HTTPException, Query, Request

from quiz_relay.config import Settings, load_settings
from quiz_relay.core import IMAGE_MIME_TYPES, available_modes
from quiz_relay.errors import AiResponseError, ConfigError, InvalidImageError, QuizRelayError, UnknownModeError
from quiz_relay.service import dispatch_relays, solution_payload, solve_image

CONTENT_TYPE_SUFFIXES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

app = FastAPI(title="Quiz Relay API")


def _settings() -> Settings:
    config = os.environ.get("QUIZ_RELAY_CONFIG")
    return load_settings(Path(config).expanduser() if config else None)


def _require_api_key(settings: Settings, api_key: str | None) -> None:
    if not settings.api_keys:
        raise HTTPException(status_code=500, detail="No API keys configured in [api].keys.")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header.")
    if not any(hmac.compare_digest(api_key, configured) for configured in settings.api_keys):
        raise HTTPException(status_code=403, detail="Invalid API key.")


def _error_status(exc: QuizRelayError) -> int:
    if isinstance(exc, UnknownModeError):
        return 404
    if isinstance(exc, InvalidImageError):
        return 400
    if isinstance(exc, ConfigError):
        return 500
    if isinstance(exc, AiResponseError):
        return 502
    return 500


def _settings_for_request() -> Settings:
    try:
        return _settings()
    except QuizRelayError as exc:
        raise HTTPException(status_code=_error_status(exc), detail=str(exc)) from exc


def _save_upload(settings: Settings, mode: str, content_type: str, body: bytes) -> Path:
    suffix = CONTENT_TYPE_SUFFIXES.get(content_type.lower())
    if suffix is None or suffix not in IMAGE_MIME_TYPES:
        supported = ", ".join(sorted(CONTENT_TYPE_SUFFIXES))
        raise InvalidImageError(f"Unsupported Content-Type '{content_type}'. Supported: {supported}")
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/modes")
def modes(x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None) -> dict[str, list[str]]:
    settings = _settings_for_request()
    _require_api_key(settings, x_api_key)
    return {"modes": available_modes(settings.prompts_dir)}


@app.post("/solve/{mode}")
async def solve(
    mode: str,
    request: Request,
    relay: Annotated[list[str] | None, Query()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> dict[str, Any]:
    settings = _settings_for_request()
    _require_api_key(settings, x_api_key)

    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip()
    try:
        image_path = _save_upload(settings, mode, content_type, await request.body())
        solution = solve_image(settings, mode, image_path)
        payload = solution_payload(mode, image_path, solution)
        relay_names = relay or []
        if relay_names:
            payload["relays"] = dispatch_relays(settings, relay_names, payload["pulses"])
        return payload
    except QuizRelayError as exc:
        raise HTTPException(status_code=_error_status(exc), detail=str(exc)) from exc
