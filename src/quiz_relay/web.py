from __future__ import annotations

import hmac
import os
import sys
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Header, HTTPException, Query, Request

from quiz_relay.app import run_solve
from quiz_relay.config import Settings, load_settings
from quiz_relay.core import available_modes
from quiz_relay.errors import QuizRelayError, error_status
from quiz_relay.runtime_log import log_event, web_log_path
from quiz_relay.uploads import save_upload

app = FastAPI(title="Quiz Relay API")


@app.middleware("http")
async def log_request(request: Request, call_next):
    client = request.client
    client_addr = f"{client.host}:{client.port}" if client else "unknown"
    print(f"request received from {client_addr}: {request.method} {request.url.path}", file=sys.stderr, flush=True)
    return await call_next(request)


def _settings() -> Settings:
    config = os.environ.get("QUIZ_RELAY_CONFIG")
    return load_settings(Path(config).expanduser() if config else None)


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
    relay_names = relay or []
    try:
        image_path = save_upload(settings, mode, normalized_content_type, await request.body())
        response = run_solve(settings, mode, relay_names, image=image_path)
        log_event(
            "web.solve.response",
            {
                "mode": mode,
                "relays": relay_names,
                "response": response,
            },
            path=web_log_path(settings.api_upload_dir),
        )
        return response
    except QuizRelayError as exc:
        status = error_status(exc)
        log_event(
            "web.solve.error",
            {
                "mode": mode,
                "relays": relay_names,
                "status": status,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
            path=web_log_path(settings.api_upload_dir),
        )
        raise HTTPException(status_code=status, detail=str(exc)) from exc
