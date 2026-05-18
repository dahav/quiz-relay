from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from quiz_relay.config import Settings, load_settings
from quiz_relay.core import available_modes, solve, validate_mode
from quiz_relay.mouse import SUPPORTED_EVENTS, MouseEvent, listen_for_mouse_event
from quiz_relay.relays import available_relays, build_relay
from quiz_relay.solution import Option, QuestionSolution, Solution

RELAY_TEST_SEQUENCE: tuple[str, ...] = ("C",)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quiz-relay")
    parser.add_argument(
        "--config",
        help="Path to config.toml (default: ./config.toml)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    solve_cmd = sub.add_parser("solve", help="Run one screenshot-to-relay cycle")
    _add_mode_arg(solve_cmd)
    _add_relay_arg(solve_cmd)
    solve_cmd.add_argument(
        "--image",
        help="Use this image file instead of capturing a screenshot.",
    )

    listen = sub.add_parser("listen", help="Run solve on each mouse event")
    _add_mode_arg(listen)
    _add_relay_arg(listen)
    listen.add_argument("--event", choices=sorted(SUPPORTED_EVENTS))
    listen.add_argument("--scan", action="store_true", help="Print each detected event")
    listen.add_argument("--list-events", action="store_true", help="List supported events")

    sub.add_parser("modes", help="List available prompt modes")
    sub.add_parser("relays", help="List available relay modules")

    relay_test = sub.add_parser(
        "relay-test",
        help=(
            "Send a fixed test signal (3 pulses) to the configured relay. "
            "Useful for verifying http and keyboard_led wiring without solving a question."
        ),
    )
    _add_relay_arg(relay_test)
    return parser


def _add_mode_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--mode",
        help="Prompt mode (file stem in prompts/).",
    )


def _add_relay_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--relay",
        action="append",
        default=[],
        help=(
            "Relay module to dispatch the solution to. "
            "Repeat to use multiple (e.g. --relay http --relay keyboard_led). "
            "Available: " + (", ".join(available_relays()) or "(none)")
        ),
    )


def _resolve_mode(args: argparse.Namespace) -> str:
    mode = (args.mode or "").strip()
    if not mode:
        raise SystemExit("--mode is required.")
    return mode


def _resolve_config(args: argparse.Namespace) -> Path | None:
    return Path(args.config).expanduser() if args.config else None


def _dispatch_relays(names: list[str], settings: Settings, solution: Solution) -> dict[str, Any]:
    results: dict[str, Any] = {}
    if not names:
        print("[relay] none selected (pass --relay <name> to dispatch)", flush=True)
        return results
    print(f"[relay] dispatching to: {', '.join(names)}", flush=True)
    for name in names:
        section = settings.relays.get(name, {})
        print(f"[relay:{name}] sending...", flush=True)
        try:
            relay = build_relay(name, section)
            result = relay.send(solution)
            results[name] = result
            status = "OK" if result.get("sent") else "FAILED"
            print(f"[relay:{name}] {status} {result}", flush=True)
        except SystemExit as exc:
            results[name] = {"sent": False, "error": str(exc)}
            print(f"[relay:{name}] FAILED {exc}", flush=True)
        except Exception as exc:
            results[name] = {"sent": False, "error": str(exc)}
            print(f"[relay:{name}] FAILED {exc}", flush=True)
    return results


def _build_result(
    solution: Solution,
    source: Path,
    source_key: str,
    mode: str,
    relay_results: dict[str, Any],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "mode": mode,
        source_key: str(source),
        "solution": solution.to_dict(),
    }
    if relay_results:
        result["relays"] = relay_results
    return result


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "solve":
        return _cmd_solve(args)
    if args.command == "listen":
        return _cmd_listen(args)
    if args.command == "modes":
        return _cmd_modes(args)
    if args.command == "relays":
        return _cmd_relays()
    if args.command == "relay-test":
        return _cmd_relay_test(args)
    return 1


def _cmd_solve(args: argparse.Namespace) -> int:
    settings = load_settings(_resolve_config(args))
    image = Path(args.image).expanduser() if args.image else None
    mode = _resolve_mode(args)
    solution, source, source_key = solve(settings, mode, image=image)
    relay_results = _dispatch_relays(args.relay, settings, solution)
    result = _build_result(solution, source, source_key, mode, relay_results)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _cmd_listen(args: argparse.Namespace) -> int:
    if args.list_events:
        for name, description in SUPPORTED_EVENTS.items():
            print(f"{name}: {description}")
        return 0

    settings = load_settings(_resolve_config(args))

    if args.scan:
        print("Scanning mouse events. Stop with Ctrl+C.", flush=True)
        listen_for_mouse_event("middle-click", lambda _event: None, scan=True)
        return 0

    mode = _resolve_mode(args)
    validate_mode(settings.prompts.dir, mode)
    event_name = args.event or settings.mouse.event
    relay_names: list[str] = args.relay

    def on_event(event: MouseEvent) -> None:
        solution, source, source_key = solve(settings, mode)
        relay_results = _dispatch_relays(relay_names, settings, solution)
        result = _build_result(solution, source, source_key, mode, relay_results)
        print(json.dumps({"event": event.name, **result}, ensure_ascii=False, indent=2), flush=True)

    relay_hint = ",".join(relay_names) if relay_names else "(none)"
    print(f"Listening for {event_name} (mode={mode}, relays={relay_hint})", flush=True)
    listen_for_mouse_event(event_name, on_event)
    return 0


def _cmd_modes(args: argparse.Namespace) -> int:
    settings = load_settings(_resolve_config(args))
    modes = available_modes(settings.prompts.dir)
    if not modes:
        print(f"No modes found in {settings.prompts.dir}/", file=sys.stderr)
        return 1
    for mode in modes:
        print(mode)
    return 0


def _cmd_relay_test(args: argparse.Namespace) -> int:
    if not args.relay:
        raise SystemExit("--relay is required (e.g. --relay http or --relay keyboard_led).")
    settings = load_settings(_resolve_config(args))
    solution = _build_test_solution(RELAY_TEST_SEQUENCE)
    sequence = ",".join(RELAY_TEST_SEQUENCE)
    print(f"[relay-test] sequence={sequence}", flush=True)
    relay_results = _dispatch_relays(args.relay, settings, solution)
    result = {"test_sequence": list(RELAY_TEST_SEQUENCE), "relays": relay_results}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(r.get("sent") for r in relay_results.values()) else 1


def _build_test_solution(answers: tuple[str, ...]) -> Solution:
    options = [Option(id=a, text=f"Test option {a}") for a in answers]
    question = QuestionSolution(
        question=1,
        question_text="relay-test synthetic question",
        options=options,
        answers=list(answers),
    )
    return Solution(explanation="relay-test", confidence=1.0, questions=[question])


def _cmd_relays() -> int:
    relays = available_relays()
    if not relays:
        print("No relay modules found.", file=sys.stderr)
        return 1
    for name in relays:
        print(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
