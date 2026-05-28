from __future__ import annotations

from pathlib import Path
from typing import Any

from quiz_relay.config import Settings
from quiz_relay.core import capture_screenshot, load_mode
from quiz_relay.service import dispatch_relays, solution_payload, solve_image

RELAY_TEST_PULSES: list[int] = [3]


def run_solve(
    settings: Settings,
    mode: str,
    relay_names: list[str],
    *,
    image: Path | None = None,
    event_name: str | None = None,
) -> dict[str, Any]:
    if image is not None:
        source, source_key = image, "image"
    else:
        source, source_key = capture_screenshot(settings), "screenshot"

    solution = solve_image(settings, mode, source)
    report = solution_payload(mode, source, solution, source_key=source_key)
    if event_name is not None:
        report = {"event": event_name, **report}

    relay_results = dispatch_relays(settings, relay_names, report["pulses"])
    if relay_results:
        report["relays"] = relay_results
    return report


def validate_mode(settings: Settings, mode: str) -> None:
    load_mode(settings.prompts_dir, mode)


def run_relay_test(settings: Settings, relay_names: list[str]) -> tuple[dict[str, Any], int]:
    relay_results = dispatch_relays(settings, relay_names, RELAY_TEST_PULSES)
    report = {"test_pulses": RELAY_TEST_PULSES, "relays": relay_results}
    exit_code = 0 if all(result.get("sent") for result in relay_results.values()) else 1
    return report, exit_code
