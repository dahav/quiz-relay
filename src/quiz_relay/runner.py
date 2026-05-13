from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Any, Callable

from quiz_relay.ai import analyze_image, parse_ai_response, validate_solution
from quiz_relay.capture import capture_screenshot, screenshot_from_file
from quiz_relay.config import Settings
from quiz_relay.errors import AuditWriteError, QuizRelayError, RunAlreadyActiveError
from quiz_relay.models import (
    AiRawResponse,
    AiSolution,
    RelaySendResult,
    RunContext,
    RunResult,
    ScreenshotResult,
    format_timestamp,
)
from quiz_relay.relay import send_solution

CaptureFn = Callable[[Settings, RunContext], ScreenshotResult]
AnalyzeFn = Callable[[ScreenshotResult, Settings, Path], AiRawResponse]
RelayFn = Callable[[Settings, RunContext, AiSolution], RelaySendResult]
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
    """Run one full screenshot, AI analysis, validation, relay, and audit-log cycle."""
    context = RunContext.create(source=source, config_profile=settings.app.profile)
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

    screenshot: ScreenshotResult | None = None
    try:
        screenshot = _screenshot_for_run(settings, context, test_image, capture)
        result = _run_with_screenshot(settings, context, screenshot, base_dir, analyze, send)
        return _write_log_and_return(settings, result, write_log)
    except QuizRelayError as exc:
        result = RunResult.failed(context, exc, screenshot=screenshot)
        return _write_log_and_return(settings, result, write_log)
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
            os.write(self._fd, self._lock_payload(context))
        except FileExistsError as exc:
            if self._remove_stale_lock():
                self.acquire(context)
                return
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

    def _lock_payload(self, context: RunContext) -> bytes:
        return (
            json.dumps(
                {
                    "task_id": context.task_id,
                    "pid": os.getpid(),
                    "host": context.host,
                    "started_at": context.started_iso(),
                },
                ensure_ascii=False,
            )
            + "\n"
        ).encode("utf-8")

    def _remove_stale_lock(self) -> bool:
        try:
            text = self.lock_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return True
        except OSError:
            return False

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return self._unlink_stale_lock()

        if not isinstance(payload, dict):
            return self._unlink_stale_lock()

        if payload.get("host") != socket.gethostname():
            return False

        try:
            pid = int(payload["pid"])
        except (KeyError, TypeError, ValueError):
            return self._unlink_stale_lock()

        if pid <= 0 or _process_exists(pid):
            return False
        return self._unlink_stale_lock()

    def _unlink_stale_lock(self) -> bool:
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            return True
        except OSError:
            return False
        return True


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def write_run_log(settings: Settings, result: RunResult) -> None:
    """Append one JSONL audit record for a completed or failed run."""
    record = run_record(settings, result)
    try:
        settings.logging.runs_file.parent.mkdir(parents=True, exist_ok=True)
        with settings.logging.runs_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        raise AuditWriteError(f"Could not write run log: {exc}") from exc


def run_record(settings: Settings, result: RunResult) -> dict[str, Any]:
    """Convert a run result into the JSON-serializable audit record shape."""
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
    _add_screenshot_record(record, result)
    _add_solution_record(record, settings, result)
    _add_relay_record(record, result)
    _add_error_record(record, result)
    return record


def _screenshot_for_run(
    settings: Settings,
    context: RunContext,
    test_image: Path | None,
    capture: CaptureFn,
) -> ScreenshotResult:
    if test_image is not None:
        return screenshot_from_file(test_image)
    return capture(settings, context)


def _run_with_screenshot(
    settings: Settings,
    context: RunContext,
    screenshot: ScreenshotResult,
    base_dir: Path,
    analyze: AnalyzeFn,
    send: RelayFn,
) -> RunResult:
    raw_response = analyze(screenshot, settings, base_dir)
    solution = validate_solution(parse_ai_response(raw_response))
    relay_result = send(settings, context, solution)
    return _result_from_relay(context, screenshot, solution, relay_result)


def _result_from_relay(
    context: RunContext,
    screenshot: ScreenshotResult,
    solution: AiSolution,
    relay_result: RelaySendResult,
) -> RunResult:
    if relay_result.sent or relay_result.error == "disabled":
        return RunResult.success(context, screenshot, solution, relay_result)
    return RunResult.partial(context, screenshot, solution, relay_result)


def _write_log_and_return(settings: Settings, result: RunResult, write_log: LogFn) -> RunResult:
    write_log(settings, result)
    return result


def _add_screenshot_record(record: dict[str, Any], result: RunResult) -> None:
    if result.screenshot:
        record["screenshot_path"] = result.screenshot.path


def _add_solution_record(record: dict[str, Any], settings: Settings, result: RunResult) -> None:
    if result.solution:
        record["explanation"] = result.solution.explanation
        record["answers"] = result.solution.answer_dicts()
        record["confidence"] = result.solution.confidence
        if settings.app.save_ai_raw_response:
            record["ai_raw_response"] = result.solution.raw_response


def _add_relay_record(record: dict[str, Any], result: RunResult) -> None:
    if result.relay_result:
        record["http_relay"] = result.relay_result.as_dict()


def _add_error_record(record: dict[str, Any], result: RunResult) -> None:
    if result.error:
        record["error_stage"] = result.error.stage
        record["error_type"] = result.error.error_type
        record["error_message"] = result.error.message


def _analyze_with_settings(image: ScreenshotResult, settings: Settings, base_dir: Path) -> AiRawResponse:
    return analyze_image(image, settings.ai, base_dir=base_dir)


def _send_with_settings(settings: Settings, context: RunContext, solution: AiSolution) -> RelaySendResult:
    return send_solution(settings.http_relay, context, solution)
