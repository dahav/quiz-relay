from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from quiz_relay.ai import analyze_image, parse_ai_response, validate_solution
from quiz_relay.capture import capture_screenshot, screenshot_from_file
from quiz_relay.config import Settings
from quiz_relay.errors import AuditWriteError, QuizRelayError, RunAlreadyActiveError
from quiz_relay.models import AiRawResponse, RelaySendResult, RunContext, RunResult, ScreenshotResult, format_timestamp
from quiz_relay.relay import send_solution

CaptureFn = Callable[[Settings, RunContext], ScreenshotResult]
AnalyzeFn = Callable[[ScreenshotResult, Settings, Path], AiRawResponse]
RelayFn = Callable[[Settings, RunContext, Any], RelaySendResult]
LogFn = Callable[[Settings, RunResult], None]


def run_once(
    settings: Settings,
    source: str = "cli",
    test_image: Path | None = None,
    base_dir: Path = Path("."),
    capture: CaptureFn | None = None,
    analyze: AnalyzeFn | None = None,
    send: RelayFn | None = None,
    write_log: LogFn | None = None,
) -> RunResult:
    context = RunContext.create(source=source, config_profile=settings.app.profile)
    screenshot: ScreenshotResult | None = None
    capture = capture or capture_screenshot
    analyze = analyze or _analyze_with_settings
    send = send or _send_with_settings
    write_log = write_log or write_run_log
    lock = RunLock(settings.app.runtime_directory / "quiz-relay.lock", settings.app.allow_parallel_runs)

    try:
        lock.acquire(context)
    except RunAlreadyActiveError as exc:
        result = RunResult.locked(context, exc)
        write_log(settings, result)
        return result

    try:
        screenshot = screenshot_from_file(test_image) if test_image is not None else capture(settings, context)
        raw_response = analyze(screenshot, settings, base_dir)
        solution = validate_solution(parse_ai_response(raw_response))
        relay_result = send(settings, context, solution)
        if relay_result.sent or relay_result.error == "disabled":
            result = RunResult.success(context, screenshot, solution, relay_result)
        else:
            result = RunResult.partial(context, screenshot, solution, relay_result)
        write_log(settings, result)
        return result
    except QuizRelayError as exc:
        result = RunResult.failed(context, exc, screenshot=screenshot)
        write_log(settings, result)
        return result
    finally:
        lock.release()


class RunLock:
    def __init__(self, lock_path: Path, allow_parallel_runs: bool = False) -> None:
        self.lock_path = lock_path
        self.allow_parallel_runs = allow_parallel_runs
        self._fd: int | None = None

    def acquire(self, context: RunContext) -> None:
        if self.allow_parallel_runs:
            return
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(self._fd, f"{context.task_id}\n".encode("utf-8"))
        except FileExistsError as exc:
            raise RunAlreadyActiveError("A run is already active.") from exc

    def release(self) -> None:
        if self.allow_parallel_runs or self._fd is None:
            return
        os.close(self._fd)
        self._fd = None
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass


def write_run_log(settings: Settings, result: RunResult) -> None:
    record = run_record(settings, result)
    try:
        settings.logging.runs_file.parent.mkdir(parents=True, exist_ok=True)
        with settings.logging.runs_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        raise AuditWriteError(f"Could not write run log: {exc}") from exc


def run_record(settings: Settings, result: RunResult) -> dict[str, Any]:
    context = result.context
    record: dict[str, Any] = {
        "task_id": context.task_id,
        "source": context.source,
        "started_at": context.started_iso(),
        "finished_at": format_timestamp(result.finished_at),
        "duration_ms": result.duration_ms,
        "host": context.host,
        "user": context.user,
        "config_profile": context.config_profile,
        "status": result.status,
    }
    if result.screenshot:
        record["screenshot_path"] = result.screenshot.path
    if result.solution:
        record["explanation"] = result.solution.explanation
        record["answers"] = [{"question": item.question, "answers": item.answers} for item in result.solution.answers]
        record["confidence"] = result.solution.confidence
        if settings.app.save_ai_raw_response:
            record["ai_raw_response"] = result.solution.raw_response
    if result.relay_result:
        record["http_relay"] = {
            "sent": result.relay_result.sent,
            "status_code": result.relay_result.status_code,
            "response_body": result.relay_result.response_body,
            "duration_ms": result.relay_result.duration_ms,
            "error": result.relay_result.error,
        }
    if result.error:
        record["error_stage"] = result.error.stage
        record["error_type"] = result.error.error_type
        record["error_message"] = result.error.message
    return record


def _analyze_with_settings(image: ScreenshotResult, settings: Settings, base_dir: Path) -> AiRawResponse:
    return analyze_image(image, settings.ai, base_dir=base_dir)


def _send_with_settings(settings: Settings, context: RunContext, solution: Any) -> RelaySendResult:
    return send_solution(settings.http_relay, context, solution)
