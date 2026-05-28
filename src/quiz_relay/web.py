from __future__ import annotations

import asyncio
import hmac
import os
import sys
from pathlib import Path
from time import perf_counter
from typing import Annotated, Any

from fastapi import FastAPI, Header, HTTPException, Query, Request
from starlette.requests import ClientDisconnect

from quiz_relay.app import log_solve_failure, run_solve
from quiz_relay.config import Settings, load_settings
from quiz_relay.core import available_modes
from quiz_relay.debug import DebugSink
from quiz_relay.errors import InvalidImageError, QuizRelayError, error_status
from quiz_relay.uploads import save_upload

app = FastAPI(title="Quiz Relay API")

BODY_READ_IDLE_TIMEOUT_SECONDS = 30.0


def _debug() -> DebugSink:
    log_path = Path(os.environ.get("QUIZ_RELAY_DEBUG_LOG", "runtime/quiz-relay.log")).expanduser()
    return DebugSink(enabled=True, stream=sys.stderr, log_path=log_path)


def _settings(debug: DebugSink | None = None) -> Settings:
    debug = debug or DebugSink()
    config = os.environ.get("QUIZ_RELAY_CONFIG")
    path = Path(config).expanduser() if config else None
    display_path = path or Path("config.toml")
    debug.line(f"settings load path={display_path}")
    settings = load_settings(path)
    debug.line(
        f"settings loaded prompts_dir={settings.prompts_dir} upload_dir={settings.api_upload_dir} "
        f"api_keys={len(settings.api_keys)} model={settings.ai_model} timeout={settings.ai_timeout_seconds}"
    )
    return settings


def _settings_for_request(debug: DebugSink | None = None) -> Settings:
    try:
        return _settings(debug)
    except QuizRelayError as exc:
        status_code = error_status(exc)
        if debug:
            debug.line(f"settings failed status={status_code} error={exc}")
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


def _require_api_key(settings: Settings, api_key: str | None, debug: DebugSink | None = None) -> None:
    debug = debug or DebugSink()
    debug.line(f"auth check configured_keys={len(settings.api_keys)} header_present={bool(api_key)}")
    if not settings.api_keys:
        debug.line("auth failed reason=no_configured_keys")
        raise HTTPException(status_code=500, detail="No API keys configured in [api].keys.")
    if not api_key:
        debug.line("auth failed reason=missing_header")
        raise HTTPException(status_code=401, detail="Missing X-API-Key header.")
    if not any(hmac.compare_digest(api_key, configured) for configured in settings.api_keys):
        debug.line("auth failed reason=invalid_key")
        raise HTTPException(status_code=403, detail="Invalid API key.")
    debug.line("auth ok")


async def _read_body(
    request: Request,
    settings: Settings,
    debug: DebugSink,
    *,
    expected_bytes: int | None = None,
) -> bytes:
    started = perf_counter()
    chunks: list[bytes] = []
    total = 0
    chunk_count = 0
    debug.line(
        f"body read start max_bytes={settings.api_max_upload_bytes} "
        f"expected_bytes={expected_bytes} idle_timeout={BODY_READ_IDLE_TIMEOUT_SECONDS}"
    )
    stream = request.stream().__aiter__()
    while True:
        try:
            chunk = await asyncio.wait_for(anext(stream), timeout=BODY_READ_IDLE_TIMEOUT_SECONDS)
        except StopAsyncIteration:
            break
        except ClientDisconnect as exc:
            raise InvalidImageError(_incomplete_body_message("Client disconnected", total, expected_bytes)) from exc
        except asyncio.TimeoutError as exc:
            raise InvalidImageError(_incomplete_body_message("Upload stalled", total, expected_bytes)) from exc

        if not chunk:
            continue
        chunk_count += 1
        total += len(chunk)
        elapsed_ms = (perf_counter() - started) * 1000
        debug.line(f"body chunk index={chunk_count} bytes={len(chunk)} total={total} elapsed_ms={elapsed_ms:.1f}")
        if total > settings.api_max_upload_bytes:
            raise InvalidImageError(f"Image exceeds max_upload_bytes ({settings.api_max_upload_bytes}).")
        chunks.append(chunk)

    if expected_bytes is not None and total != expected_bytes:
        raise InvalidImageError(_incomplete_body_message("Upload ended early", total, expected_bytes))

    elapsed_ms = (perf_counter() - started) * 1000
    debug.line(f"body read done chunks={chunk_count} bytes={total} elapsed_ms={elapsed_ms:.1f}")
    return b"".join(chunks)


def _incomplete_body_message(reason: str, total: int, expected_bytes: int | None) -> str:
    if expected_bytes is None:
        return f"{reason} after {total} bytes."
    remaining = max(expected_bytes - total, 0)
    return f"{reason} after {total} of {expected_bytes} bytes ({remaining} missing)."


def _content_length_value(content_length: str | None) -> int | None:
    if not content_length:
        return None
    try:
        value = int(content_length)
    except ValueError:
        return None
    return value if value >= 0 else None


@app.middleware("http")
async def log_request(request: Request, call_next):
    debug = _debug()
    started = perf_counter()
    client = request.client
    client_addr = f"{client.host}:{client.port}" if client else "unknown"
    content_type = request.headers.get("content-type", "")
    content_length = request.headers.get("content-length", "unknown")
    debug.line(
        f"request start client={client_addr} method={request.method} path={request.url.path} "
        f"query={request.url.query!r} content_type={content_type!r} content_length={content_length}"
    )
    try:
        response = await call_next(request)
    except Exception as exc:
        elapsed_ms = (perf_counter() - started) * 1000
        debug.exception(
            f"request exception client={client_addr} method={request.method} path={request.url.path} "
            f"elapsed_ms={elapsed_ms:.1f} error={exc}",
            exc,
        )
        raise
    elapsed_ms = (perf_counter() - started) * 1000
    debug.line(
        f"request done client={client_addr} method={request.method} path={request.url.path} "
        f"status={response.status_code} elapsed_ms={elapsed_ms:.1f}"
    )
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/modes")
def modes(x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None) -> dict[str, list[str]]:
    debug = _debug()
    settings = _settings_for_request(debug)
    _require_api_key(settings, x_api_key, debug)
    modes_list = available_modes(settings.prompts_dir)
    debug.line(f"modes response count={len(modes_list)} modes={modes_list}")
    return {"modes": modes_list}


@app.post("/solve/{mode}")
async def solve(
    mode: str,
    request: Request,
    relay: Annotated[list[str] | None, Query()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    content_type: Annotated[str | None, Header(alias="Content-Type")] = None,
    content_length: Annotated[str | None, Header(alias="Content-Length")] = None,
) -> dict[str, Any]:
    debug = _debug()
    expected_bytes = _content_length_value(content_length)
    debug.line(
        f"solve route entered mode={mode} relays={relay or []} "
        f"content_type={content_type!r} content_length={content_length!r} expected_bytes={expected_bytes}"
    )
    settings = _settings_for_request(debug)
    _require_api_key(settings, x_api_key, debug)

    image_path: Path | None = None
    try:
        body = await _read_body(request, settings, debug, expected_bytes=expected_bytes)
        debug.line(f"solve request body_complete mode={mode} body_bytes={len(body)} content_type={content_type!r}")
        normalized_content_type = (content_type or "").split(";", 1)[0].strip()
        debug.line(f"upload validate content_type={normalized_content_type!r} bytes={len(body)}")
        image_path = save_upload(settings, mode, normalized_content_type, body)
        debug.line(f"upload saved path={image_path} bytes={len(body)}")
        return run_solve(
            settings,
            mode,
            relay or [],
            image=image_path,
            debug=debug,
            log_report=True,
        )
    except QuizRelayError as exc:
        status_code = error_status(exc)
        log_solve_failure(mode, image_path, status_code, exc, debug=debug)
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except Exception as exc:
        log_solve_failure(mode, image_path, 500, exc, debug=debug)
        debug.exception(f"solve unexpected exception mode={mode} image={image_path} error={exc}", exc)
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {type(exc).__name__}") from exc
