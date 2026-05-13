from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from quiz_relay.config import load_settings
from quiz_relay.core import available_modes, solve, validate_mode
from quiz_relay.mouse import SUPPORTED_EVENTS, MouseEvent, listen_for_mouse_event


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quiz-relay")
    parser.add_argument(
        "--config",
        help="Path to config.toml (default: ./config.toml)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    solve_cmd = sub.add_parser("solve", help="Run one screenshot-to-relay cycle")
    _add_mode_arg(solve_cmd)
    solve_cmd.add_argument(
        "--image",
        help="Use this image file instead of capturing a screenshot.",
    )

    listen = sub.add_parser("listen", help="Run solve on each mouse event")
    _add_mode_arg(listen)
    listen.add_argument("--event", choices=sorted(SUPPORTED_EVENTS))
    listen.add_argument("--scan", action="store_true", help="Print each detected event")
    listen.add_argument("--list-events", action="store_true", help="List supported events")

    sub.add_parser("modes", help="List available prompt modes")
    return parser


def _add_mode_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--mode",
        help="Prompt mode (file stem in prompts/).",
    )


def _resolve_mode(args: argparse.Namespace) -> str:
    mode = (args.mode or "").strip()
    if not mode:
        raise SystemExit("--mode is required.")
    return mode


def _resolve_config(args: argparse.Namespace) -> Path | None:
    return Path(args.config).expanduser() if args.config else None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "solve":
        return _cmd_solve(args)
    if args.command == "listen":
        return _cmd_listen(args)
    if args.command == "modes":
        return _cmd_modes(args)
    return 1


def _cmd_solve(args: argparse.Namespace) -> int:
    settings = load_settings(_resolve_config(args))
    image = Path(args.image).expanduser() if args.image else None
    result = solve(settings, _resolve_mode(args), image=image)
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

    def on_event(event: MouseEvent) -> None:
        result = solve(settings, mode)
        print(json.dumps({"event": event.name, **result}, ensure_ascii=False, indent=2), flush=True)

    print(f"Listening for {event_name} (mode={mode})", flush=True)
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


if __name__ == "__main__":
    sys.exit(main())
