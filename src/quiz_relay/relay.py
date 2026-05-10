from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict
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


def send_solution(config: HttpRelayConfig, context: RunContext, solution: AiSolution) -> RelaySendResult:
    if not config.enabled:
        return RelaySendResult.disabled()

    payload = build_relay_payload(config, context, solution)
    request = build_relay_request(config, payload)
    attempts = config.retries + 1
    last_error = None
    started = time.monotonic()

    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
                response_body = response.read().decode("utf-8", errors="replace")
                duration_ms = int((time.monotonic() - started) * 1000)
                success = 200 <= response.status < 300
                return RelaySendResult(
                    sent=success,
                    status_code=response.status,
                    response_body=response_body,
                    duration_ms=duration_ms,
                    error=None if success else f"HTTP {response.status}",
                )
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            if 400 <= exc.code < 500:
                duration_ms = int((time.monotonic() - started) * 1000)
                return RelaySendResult(False, exc.code, body_text, duration_ms, f"HTTP {exc.code}")
            last_error = f"HTTP {exc.code}: {body_text}"
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = str(exc)
        if attempt + 1 < attempts:
            time.sleep(0.1)

    return RelaySendResult(
        sent=False,
        status_code=None,
        response_body=None,
        duration_ms=int((time.monotonic() - started) * 1000),
        error=last_error or "HTTP relay send failed",
    )


def build_relay_payload(config: HttpRelayConfig, context: RunContext, solution: AiSolution) -> dict[str, Any]:
    fields = config.fields or DEFAULT_RELAY_FIELDS
    created_at = format_timestamp(local_now())
    payload: dict[str, Any] = {}
    for target, expression in fields.items():
        value = _resolve_field(expression, context, solution, created_at)
        if value is not None:
            payload[target] = value
    return payload


def build_relay_request(config: HttpRelayConfig, payload: dict[str, Any]) -> urllib.request.Request:
    if config.mode == "query":
        query = urllib.parse.urlencode({key: _query_value(value) for key, value in payload.items()})
        separator = "&" if urllib.parse.urlparse(config.url).query else "?"
        return urllib.request.Request(f"{config.url}{separator}{query}", method="GET")

    body = json.dumps(payload).encode("utf-8")
    return urllib.request.Request(
        config.url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )


def _resolve_field(expression: str, context: RunContext, solution: AiSolution, created_at: str) -> Any:
    if expression == "solution.answers":
        return [{"question": item.question, "answers": item.answers} for item in solution.answers]
    if expression == "solution.answer_letters":
        return [answer for item in solution.answers for answer in item.answers]
    if expression == "solution.answers_text":
        return ",".join(answer for item in solution.answers for answer in item.answers)
    if expression == "solution.explanation":
        return solution.explanation
    if expression == "solution.confidence":
        return solution.confidence
    if expression == "solution.raw_response":
        return solution.raw_response
    if expression == "context.task_id":
        return context.task_id
    if expression == "context.source":
        return context.source
    if expression == "context.started_at":
        return context.started_iso()
    if expression == "context.config_profile":
        return context.config_profile
    if expression == "context.host":
        return context.host
    if expression == "context.user":
        return context.user
    if expression == "meta.created_at":
        return created_at
    if expression.startswith("literal:"):
        return expression.removeprefix("literal:")
    if expression.startswith("solution."):
        value = getattr(solution, expression.removeprefix("solution."), None)
        return asdict(value) if hasattr(value, "__dataclass_fields__") else value
    if expression.startswith("context."):
        return getattr(context, expression.removeprefix("context."), None)
    return None


def _query_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, int | float | bool):
        return str(value).lower() if isinstance(value, bool) else str(value)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
