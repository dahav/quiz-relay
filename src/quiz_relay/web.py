from __future__ import annotations

import hmac
import json
import os
import sys
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response

from quiz_relay.app import run_solve
from quiz_relay.config import Settings, load_settings
from quiz_relay.core import available_modes
from quiz_relay.errors import QuizRelayError, error_status
from quiz_relay.runtime_log import WEB_LOG, log_event, web_log_path
from quiz_relay.uploads import save_upload

app = FastAPI(title="Quiz Relay API")


@app.middleware("http")
async def log_request(request: Request, call_next):
    client = request.client
    client_addr = f"{client.host}:{client.port}" if client else "unknown"
    print(f"request received from {client_addr}: {request.method} {request.url.path}", file=sys.stderr, flush=True)

    response = await call_next(request)
    body = b"".join([chunk async for chunk in response.body_iterator])
    log_event(
        "web.response",
        {
            "client": client_addr,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "response": _logged_response_body(body),
        },
        path=_web_log_path(),
    )
    return Response(
        content=body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
    )


def _settings() -> Settings:
    config = os.environ.get("QUIZ_RELAY_CONFIG")
    return load_settings(Path(config).expanduser() if config else None)


def _web_log_path() -> Path:
    try:
        return web_log_path(_settings().api_upload_dir)
    except QuizRelayError:
        return WEB_LOG


def _logged_response_body(body: bytes) -> Any:
    text = body.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _settings_for_request() -> Settings:
    try:
        return _settings()
    except QuizRelayError as exc:
        raise HTTPException(status_code=error_status(exc), detail=str(exc)) from exc


def _require_api_key(settings: Settings, api_key: str | None) -> None:
    if not settings.api_keys:
        raise HTTPException(status_code=500, detail="No API keys configured in [api].keys.")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header.")
    if not any(hmac.compare_digest(api_key, configured) for configured in settings.api_keys):
        raise HTTPException(status_code=403, detail="Invalid API key.")


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
    content_type: Annotated[str | None, Header(alias="Content-Type")] = None,
) -> dict[str, Any]:
    settings = _settings_for_request()
    _require_api_key(settings, x_api_key)

    normalized_content_type = (content_type or "").split(";", 1)[0].strip()
    try:
        image_path = save_upload(settings, mode, normalized_content_type, await request.body())
        return run_solve(settings, mode, relay or [], image=image_path)
    except QuizRelayError as exc:
        raise HTTPException(status_code=error_status(exc), detail=str(exc)) from exc
