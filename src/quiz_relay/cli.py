from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from quiz_relay.app import build_pipeline, build_screenshot_service
from quiz_relay.config import load_settings
from quiz_relay.esp32.esp32_client import Esp32Client
from quiz_relay.esp32.payload_builder import Esp32PayloadBuilder
from quiz_relay.errors import ConfigurationError, QuizRelayError
from quiz_relay.pipeline.result_models import PipelineResult
from quiz_relay.pipeline.run_context import RunContext
from quiz_relay.triggers.mouse_listener import SUPPORTED_EVENTS, MouseEvent, MouseEventListener


def _print_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _result_to_stdout(result: PipelineResult) -> dict:
    data = {
        "status": result.status,
        "task_id": result.context.task_id,
    }
    if result.solution:
        data["answers"] = [
            {"question": item.question, "answers": item.answers}
            for item in result.solution.answers
        ]
        data["confidence"] = result.solution.confidence
    if result.esp32_result:
        data["esp32_sent"] = result.esp32_result.sent
        data["esp32_error"] = result.esp32_result.error
    if result.error:
        data["error"] = {
            "stage": result.error.stage,
            "type": result.error.error_type,
            "message": result.error.message,
        }
    return data


def _exit_code(result: PipelineResult) -> int:
    if result.status == "success":
        return 0
    if result.status == "partial":
        return 6
    if result.status == "locked":
        return 7
    if result.error and result.error.stage == "configuration":
        return 2
    if result.error and result.error.stage == "screenshot":
        return 3
    if result.error and result.error.stage == "ai_request":
        return 4
    if result.error and result.error.stage in {"ai_parse", "solution_validation"}:
        return 5
    if result.error and result.error.stage == "esp32_send":
        return 6
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quiz-relay")
    parser.add_argument("--config", type=Path, help="Pfad zur Konfiguration")
    parser.add_argument("--profile", help="Konfigurationsprofil")
    parser.add_argument("--verbose", action="store_true", help="Ausfuehrlichere Logs")
    parser.add_argument("--quiet", action="store_true", help="Nur Fehler ausgeben")

    subparsers = parser.add_subparsers(dest="command", required=True)

    solve = subparsers.add_parser("solve", help="Fuehrt einen vollstaendigen Pipeline-Run aus")
    solve.add_argument("--source", default="cli")
    solve.add_argument("--no-esp32", action="store_true")
    solve.add_argument("--save-screenshot", choices=["true", "false"])
    solve.add_argument("--test-image", type=Path)

    subparsers.add_parser("test-screenshot", help="Erstellt nur einen Screenshot")
    subparsers.add_parser("list-monitors", help="Listet erkannte Monitore")
    subparsers.add_parser("config-check", help="Prueft die Konfiguration")
    subparsers.add_parser("doctor", help="Gibt Diagnoseinformationen aus")

    test_esp = subparsers.add_parser("test-esp", help="Sendet ein Testpayload an den ESP32")
    test_esp.add_argument("--source", default="test")

    listen = subparsers.add_parser("listen-mouse", help="Lauscht auf ein Mouse-Event")
    listen.add_argument("--event", choices=sorted(SUPPORTED_EVENTS))
    listen.add_argument("--scan", action="store_true")
    listen.add_argument("--list-events", action="store_true")

    parse = subparsers.add_parser("parse-response", help="Parst eine gespeicherte KI-Antwort")
    parse.add_argument("file", type=Path)
    return parser


def _settings_from_args(args: argparse.Namespace):
    settings = load_settings(args.config, args.profile)
    if getattr(args, "no_esp32", False):
        from dataclasses import replace

        settings = replace(settings, esp32=replace(settings.esp32, enabled=False))
    return settings


def cmd_solve(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    pipeline = build_pipeline(settings, base_dir=Path("."))
    result = pipeline.run(source=args.source, test_image=args.test_image)
    if not args.quiet or result.status != "success":
        _print_json(_result_to_stdout(result))
    return _exit_code(result)


def cmd_test_screenshot(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    service = build_screenshot_service(settings)
    context = RunContext.create(source="test", config_profile=settings.app.profile)
    screenshot = service.capture(context)
    _print_json({"status": "success", "path": screenshot.path, "width": screenshot.width, "height": screenshot.height})
    return 0


def cmd_list_monitors(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    service = build_screenshot_service(settings)
    monitors = service.list_monitors()
    _print_json({"status": "success", "monitors": [monitor.__dict__ for monitor in monitors]})
    return 0


def cmd_config_check(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    _print_json(
        {
            "status": "success",
            "profile": settings.app.profile,
            "screenshot_backend": settings.screenshot.backend,
            "ai_provider": settings.ai.provider,
            "esp32_enabled": settings.esp32.enabled,
        }
    )
    return 0


def cmd_test_esp(args: argparse.Namespace) -> int:
    from quiz_relay.ai.models import AiSolution, QuestionAnswer

    settings = _settings_from_args(args)
    context = RunContext.create(source=args.source, config_profile=settings.app.profile)
    client = Esp32Client(settings.esp32, Esp32PayloadBuilder(settings.esp32))
    result = client.send_solution(
        context,
        AiSolution(explanation="Testpayload", answers=[QuestionAnswer(question=1, answers=["A"])]),
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
    event_name = args.event or settings.mouse_trigger.event

    if args.scan:
        listener = MouseEventListener(event_name="middle-click", callback=lambda _event: None, scan=True)
        print("Scanne Mausevents. Beenden mit Ctrl+C.", flush=True)
        listener.start()
        return 0

    pipeline = build_pipeline(settings, base_dir=Path("."))

    def run_pipeline(event: MouseEvent) -> None:
        result = pipeline.run(source="mouse")
        _print_json({"event": event.name, **_result_to_stdout(result)})

    listener = MouseEventListener(event_name=event_name, callback=run_pipeline)
    print(f"Lausche auf Mouse-Event: {event_name}", flush=True)
    listener.start()
    return 0


def cmd_parse_response(args: argparse.Namespace) -> int:
    from quiz_relay.ai.models import AiRawResponse
    from quiz_relay.ai.response_parser import AiResponseParser
    from quiz_relay.ai.solution_validator import SolutionValidator

    text = args.file.read_text(encoding="utf-8")
    solution = SolutionValidator().validate(AiResponseParser().parse(AiRawResponse(text, "file", "file")))
    _print_json(
        {
            "status": "success",
            "explanation": solution.explanation,
            "answers": [{"question": item.question, "answers": item.answers} for item in solution.answers],
            "confidence": solution.confidence,
        }
    )
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    data = {
        "status": "success",
        "config_path": str(settings.config_path) if settings.config_path else None,
        "runtime_directory": str(settings.app.runtime_directory),
        "screenshot_backend": settings.screenshot.backend,
        "ai_provider": settings.ai.provider,
        "mouse_event": settings.mouse_trigger.event,
    }
    _print_json(data)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    commands = {
        "solve": cmd_solve,
        "test-screenshot": cmd_test_screenshot,
        "list-monitors": cmd_list_monitors,
        "config-check": cmd_config_check,
        "test-esp": cmd_test_esp,
        "listen-mouse": cmd_listen_mouse,
        "parse-response": cmd_parse_response,
        "doctor": cmd_doctor,
    }
    try:
        return commands[args.command](args)
    except ConfigurationError as exc:
        _print_json({"status": "failed", "error": {"stage": exc.stage, "type": exc.__class__.__name__, "message": str(exc)}})
        return exc.exit_code
    except QuizRelayError as exc:
        _print_json({"status": "failed", "error": {"stage": exc.stage, "type": exc.__class__.__name__, "message": str(exc)}})
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
