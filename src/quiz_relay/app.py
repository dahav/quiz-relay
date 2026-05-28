from __future__ import annotations

from pathlib import Path
from typing import Any

from quiz_relay.config import Settings
from quiz_relay.core import capture_screenshot, load_mode
from quiz_relay.debug import DebugSink
from quiz_relay.service import dispatch_relays, solution_payload, solve_image

RELAY_TEST_PULSES: list[int] = [3]


def run_solve(
    settings: Settings,
    mode: str,
    relay_names: list[str],
    *,
    image: Path | None = None,
    event_name: str | None = None,
    debug: DebugSink | None = None,
    log_report: bool = False,
) -> dict[str, Any]:
    debug = debug or DebugSink()
    debug.line(f"solve start mode={mode} relays={relay_names or []} image={image}")
    if image is not None:
        source, source_key = image, "image"
    else:
        debug.line("capture screenshot start")
        source, source_key = capture_screenshot(settings), "screenshot"
        debug.line(f"capture screenshot saved path={source}")

    debug.line(f"solve source key={source_key} path={source}")
    solution = solve_image(settings, mode, source, debug=debug)
    report = solution_payload(mode, source, solution, source_key=source_key)
    debug.line(f"solve parsed answers={report['answer_ids']} pulses={report['pulses']}")
    if event_name is not None:
        report = {"event": event_name, **report}

    relay_results = dispatch_relays(settings, relay_names, report["pulses"], debug=debug)
    if relay_results:
        report["relays"] = relay_results
    if log_report:
        debug.json(report)
    debug.line(
        f"solve done mode={mode} answer_count={len(report['answer_ids'])} "
        f"relay_count={len(report.get('relays', {}))}"
    )
    return report


def validate_mode(settings: Settings, mode: str) -> None:
    load_mode(settings.prompts_dir, mode)


def run_relay_test(
    settings: Settings,
    relay_names: list[str],
    *,
    debug: DebugSink | None = None,
) -> tuple[dict[str, Any], int]:
    debug = debug or DebugSink()
    relay_results = dispatch_relays(settings, relay_names, RELAY_TEST_PULSES, debug=debug)
    report = {"test_pulses": RELAY_TEST_PULSES, "relays": relay_results}
    exit_code = 0 if all(result.get("sent") for result in relay_results.values()) else 1
    return report, exit_code


def log_solve_failure(
    mode: str,
    image_path: Path | None,
    status_code: int,
    exc: Exception,
    *,
    debug: DebugSink | None = None,
) -> None:
    debug = debug or DebugSink()
    debug.line(f"solve failed mode={mode} image={image_path} status={status_code} error={exc}")
