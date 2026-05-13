from __future__ import annotations

import argparse
import json
import sys

from quiz_relay.config import load_settings
from quiz_relay.core import solve
from quiz_relay.mouse import SUPPORTED_EVENTS, MouseEvent, listen_for_mouse_event


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quiz-relay")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("solve", help="Run one screenshot-to-relay cycle")

    listen = sub.add_parser("listen", help="Run solve on each mouse event")
    listen.add_argument("--event", choices=sorted(SUPPORTED_EVENTS))
    listen.add_argument("--scan", action="store_true", help="Print each detected event")
    listen.add_argument("--list-events", action="store_true", help="List supported events")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "solve":
        return _cmd_solve()
    if args.command == "listen":
        return _cmd_listen(args)
    return 1


def _cmd_solve() -> int:
    settings = load_settings()
    result = solve(settings)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _cmd_listen(args: argparse.Namespace) -> int:
    if args.list_events:
        for name, description in SUPPORTED_EVENTS.items():
            print(f"{name}: {description}")
        return 0

    settings = load_settings()
    event_name = args.event or settings.mouse.event

    if args.scan:
        print("Scanning mouse events. Stop with Ctrl+C.", flush=True)
        listen_for_mouse_event("middle-click", lambda _event: None, scan=True)
        return 0

    def on_event(event: MouseEvent) -> None:
        result = solve(settings)
        print(json.dumps({"event": event.name, **result}, ensure_ascii=False, indent=2), flush=True)

    print(f"Listening for mouse event: {event_name}", flush=True)
    listen_for_mouse_event(event_name, on_event)
    return 0


if __name__ == "__main__":
    sys.exit(main())
