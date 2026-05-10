from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, is_dataclass
from typing import Any

from quiz_relay.config import HttpRelayConfig
from quiz_relay.models import AiSolution, RelaySendResult, RunContext, format_timestamp, local_now


DEFAULT_RELAY_FIELDS = {
    "task_id": "context.task_id",
    "source": "context.source",
    "answers": "solution.answers",
    "confidence": "solution.confidence",
    "created_at": "meta.created_at",
}

RETRY_DELAY_SECONDS = 0.1
MISSING_FIELD = object()


def send_solution(config: HttpRelayConfig, context: RunContext, solution: AiSolution) -> RelaySendResult:
    """Send a solution to the configured relay endpoint, including retry handling."""
    if not config.enabled:
        return RelaySendResult.disabled()

    payload = build_relay_payload(config, context, solution)
    request = build_relay_request(config, payload)
    attempts = config.retries + 1
    last_error = None
    started = time.monotonic()

    for attempt in range(attempts):
        try:
            return _send_request_once(request, config.timeout_seconds, started)
        except urllib.error.HTTPError as exc:
            body_text = _read_error_body(exc)
            if _is_client_error(exc.code):
                return _relay_result(False, exc.code, body_text, started, f"HTTP {exc.code}")
            last_error = f"HTTP {exc.code}: {body_text}"
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = str(exc)
        if attempt + 1 < attempts:
            time.sleep(RETRY_DELAY_SECONDS)

    return RelaySendResult(
        sent=False,
        status_code=None,
        response_body=None,
        duration_ms=int((time.monotonic() - started) * 1000),
        error=last_error or "HTTP relay send failed",
    )


def build_relay_payload(config: HttpRelayConfig, context: RunContext, solution: AiSolution) -> dict[str, Any]:
    """Build the outgoing relay payload from configured field expressions."""
    fields = config.fields or DEFAULT_RELAY_FIELDS
    created_at = format_timestamp(local_now())
    payload: dict[str, Any] = {}
    for target, expression in fields.items():
        value = _resolve_field(expression, context, solution, created_at)
        if value is not None:
            payload[target] = value
    return payload


def build_relay_request(config: HttpRelayConfig, payload: dict[str, Any]) -> urllib.request.Request:
    """Build either a JSON POST request or query-string GET request."""
    if config.mode == "query":
        return _query_request(config.url, payload)

    return _json_request(config.url, payload)


def _query_request(url: str, payload: dict[str, Any]) -> urllib.request.Request:
    query = urllib.parse.urlencode({key: _query_value(value) for key, value in payload.items()})
    separator = "&" if urllib.parse.urlparse(url).query else "?"
    return urllib.request.Request(f"{url}{separator}{query}", method="GET")


def _json_request(url: str, payload: dict[str, Any]) -> urllib.request.Request:
    body = json.dumps(payload).encode("utf-8")
    return urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )


def _resolve_field(expression: str, context: RunContext, solution: AiSolution, created_at: str) -> Any:
    known_value = _resolve_known_field(expression, context, solution, created_at)
    if known_value is not MISSING_FIELD:
        return known_value
    if expression.startswith("literal:"):
        return expression.removeprefix("literal:")
    if expression.startswith("solution."):
        value = getattr(solution, expression.removeprefix("solution."), None)
        return _as_payload_value(value)
    if expression.startswith("context."):
        return getattr(context, expression.removeprefix("context."), None)
    return None


def _resolve_known_field(expression: str, context: RunContext, solution: AiSolution, created_at: str) -> Any:
    fields = {
        "solution.answers": solution.answer_dicts,
        "solution.answer_letters": lambda: _answer_letters(solution),
        "solution.answers_text": lambda: ",".join(_answer_letters(solution)),
        "solution.explanation": lambda: solution.explanation,
        "solution.confidence": lambda: solution.confidence,
        "solution.raw_response": lambda: solution.raw_response,
        "context.task_id": lambda: context.task_id,
        "context.source": lambda: context.source,
        "context.started_at": context.started_iso,
        "context.config_profile": lambda: context.config_profile,
        "context.host": lambda: context.host,
        "context.user": lambda: context.user,
        "meta.created_at": lambda: created_at,
    }
    resolver = fields.get(expression)
    if resolver is None:
        return MISSING_FIELD
    return resolver()


def _answer_letters(solution: AiSolution) -> list[str]:
    return [answer for item in solution.answers for answer in item.answers]


def _as_payload_value(value: Any) -> Any:
    return asdict(value) if is_dataclass(value) else value


def _query_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, int | float | bool):
        return str(value).lower() if isinstance(value, bool) else str(value)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _send_request_once(
    request: urllib.request.Request,
    timeout_seconds: float,
    started: float,
) -> RelaySendResult:
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        response_body = response.read().decode("utf-8", errors="replace")
        success = 200 <= response.status < 300
        return _relay_result(
            sent=success,
            status_code=response.status,
            response_body=response_body,
            started=started,
            error=None if success else f"HTTP {response.status}",
        )


def _relay_result(
    sent: bool,
    status_code: int | None,
    response_body: str | None,
    started: float,
    error: str | None,
) -> RelaySendResult:
    return RelaySendResult(
        sent=sent,
        status_code=status_code,
        response_body=response_body,
        duration_ms=int((time.monotonic() - started) * 1000),
        error=error,
    )


def _read_error_body(exc: urllib.error.HTTPError) -> str:
    return exc.read().decode("utf-8", errors="replace")


def _is_client_error(status_code: int) -> bool:
    return 400 <= status_code < 500
