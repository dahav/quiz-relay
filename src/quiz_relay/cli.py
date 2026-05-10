from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Callable

from quiz_relay.ai import parse_ai_response, validate_solution
from quiz_relay.capture import capture_screenshot, list_monitors
from quiz_relay.config import Settings, load_settings
from quiz_relay.errors import ConfigurationError, QuizRelayError
from quiz_relay.models import AiRawResponse, AiSolution, QuestionAnswer, RunContext, RunResult
from quiz_relay.mouse import SUPPORTED_EVENTS, MouseEvent, listen_for_mouse_event
from quiz_relay.relay import send_solution
from quiz_relay.runner import run_once

EXIT_CODE_BY_STATUS = {
    "success": 0,
    "partial": 6,
    "locked": 7,
}

EXIT_CODE_BY_ERROR_STAGE = {
    "configuration": 2,
    "screenshot": 3,
    "ai_request": 4,
    "ai_parse": 5,
    "solution_validation": 5,
    "http_relay_send": 6,
}


def _print_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _solution_to_stdout(solution: AiSolution) -> dict[str, object]:
    return {
        "explanation": solution.explanation,
        "answers": solution.answer_dicts(),
        "confidence": solution.confidence,
    }


def _result_to_stdout(result: RunResult) -> dict:
    data = {
        "status": result.status,
        "task_id": result.context.task_id,
    }
    if result.solution:
        data["answers"] = result.solution.answer_dicts()
        data["confidence"] = result.solution.confidence
    if result.relay_result:
        data["relay_sent"] = result.relay_result.sent
        data["relay_error"] = result.relay_result.error
    if result.error:
        data["error"] = result.error.as_dict()
    return data


def _exit_code(result: RunResult) -> int:
    if result.status in EXIT_CODE_BY_STATUS:
        return EXIT_CODE_BY_STATUS[result.status]
    if result.error and result.error.stage in EXIT_CODE_BY_ERROR_STAGE:
        return EXIT_CODE_BY_ERROR_STAGE[result.error.stage]
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quiz-relay")
    parser.add_argument("--config", type=Path, help="Path to the configuration file")
    parser.add_argument("--profile", help="Configuration profile name")
    parser.add_argument("--quiet", action="store_true", help="Only print failed or partial runs")

    subparsers = parser.add_subparsers(dest="command", required=True)

    solve = subparsers.add_parser("solve", help="Run one screenshot-to-relay cycle")
    solve.add_argument("--source", default="cli")
    solve.add_argument("--no-relay", action="store_true")
    solve.add_argument("--test-image", type=Path)

    subparsers.add_parser("test-screenshot", help="Capture one screenshot")
    subparsers.add_parser("list-monitors", help="List detected monitors")
    subparsers.add_parser("config-check", help="Validate the configuration")
    subparsers.add_parser("doctor", help="Print basic diagnostics")

    test_relay = subparsers.add_parser("test-relay", help="Send a test payload to the HTTP endpoint")
    test_relay.add_argument("--source", default="test")

    listen = subparsers.add_parser("listen-mouse", help="Listen for one configured mouse event")
    listen.add_argument("--event", choices=sorted(SUPPORTED_EVENTS))
    listen.add_argument("--scan", action="store_true")
    listen.add_argument("--list-events", action="store_true")

    parse = subparsers.add_parser("parse-response", help="Parse a saved AI response")
    parse.add_argument("file", type=Path)
    return parser


def _settings_from_args(args: argparse.Namespace) -> Settings:
    settings = load_settings(args.config, args.profile)
    if getattr(args, "no_relay", False):
        settings = replace(settings, http_relay=replace(settings.http_relay, enabled=False))
    return settings


def cmd_solve(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    result = run_once(settings, source=args.source, test_image=args.test_image, base_dir=Path("."))
    if not args.quiet or result.status != "success":
        _print_json(_result_to_stdout(result))
    return _exit_code(result)


def cmd_test_screenshot(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    context = RunContext.create(source="test", config_profile=settings.app.profile)
    screenshot = capture_screenshot(settings, context)
    _print_json({"status": "success", "path": screenshot.path, "width": screenshot.width, "height": screenshot.height})
    return 0


def cmd_list_monitors(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    monitors = list_monitors(settings)
    _print_json({"status": "success", "monitors": [monitor.as_dict() for monitor in monitors]})
    return 0


def cmd_config_check(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    _print_json(
        {
            "status": "success",
            "profile": settings.app.profile,
            "screenshot_backend": "mss",
            "ai_provider": settings.ai.provider,
            "http_relay_enabled": settings.http_relay.enabled,
        }
    )
    return 0


def cmd_test_relay(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    context = RunContext.create(source=args.source, config_profile=settings.app.profile)
    result = send_solution(
        settings.http_relay,
        context,
        AiSolution(explanation="Test payload", answers=[QuestionAnswer(question=1, answers=["A"])]),
    )
    _print_json(
        {
            "status": "success" if result.sent or result.error == "disabled" else "failed",
            "sent": result.sent,
            "status_code": result.status_code,
            "response_body": result.response_body,
            "error": result.error,
        }
    )
    return 0 if result.sent or result.error == "disabled" else 6


def cmd_listen_mouse(args: argparse.Namespace) -> int:
    if args.list_events:
        for event_name, description in SUPPORTED_EVENTS.items():
            print(f"{event_name}: {description}")
        return 0

    settings = _settings_from_args(args)
    event_name = args.event or settings.mouse.event

    if args.scan:
        print("Scanning mouse events. Stop with Ctrl+C.", flush=True)
        listen_for_mouse_event(event_name="middle-click", callback=_ignore_scanned_mouse_event, scan=True)
        return 0

    def run_pipeline(event: MouseEvent) -> None:
        result = run_once(settings, source="mouse", base_dir=Path("."))
        _print_json({"event": event.name, **_result_to_stdout(result)})

    print(f"Listening for mouse event: {event_name}", flush=True)
    listen_for_mouse_event(event_name=event_name, callback=run_pipeline)
    return 0


def cmd_parse_response(args: argparse.Namespace) -> int:
    text = args.file.read_text(encoding="utf-8")
    solution = validate_solution(parse_ai_response(AiRawResponse(text, "file", "file")))
    _print_json({"status": "success", **_solution_to_stdout(solution)})
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    data = {
        "status": "success",
        "config_path": str(settings.config_path) if settings.config_path else None,
        "runtime_directory": str(settings.app.runtime_directory),
        "screenshot_backend": "mss",
        "ai_provider": settings.ai.provider,
        "mouse_event": settings.mouse.event,
    }
    _print_json(data)
    return 0


def _ignore_scanned_mouse_event(_event: MouseEvent) -> None:
    return None


def _command_handlers() -> dict[str, Callable[[argparse.Namespace], int]]:
    return {
        "solve": cmd_solve,
        "test-screenshot": cmd_test_screenshot,
        "list-monitors": cmd_list_monitors,
        "config-check": cmd_config_check,
        "test-relay": cmd_test_relay,
        "listen-mouse": cmd_listen_mouse,
        "parse-response": cmd_parse_response,
        "doctor": cmd_doctor,
    }


def _error_to_stdout(exc: QuizRelayError) -> dict[str, object]:
    return {
        "status": "failed",
        "error": {
            "stage": exc.stage,
            "type": exc.__class__.__name__,
            "message": str(exc),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _command_handlers()[args.command](args)
    except ConfigurationError as exc:
        _print_json(_error_to_stdout(exc))
        return exc.exit_code
    except QuizRelayError as exc:
        _print_json(_error_to_stdout(exc))
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
