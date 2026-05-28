from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from quiz_relay.app import run_relay_test, run_solve, validate_mode
from quiz_relay.config import load_settings
from quiz_relay.core import available_modes
from quiz_relay.errors import QuizRelayError
from quiz_relay.mouse import SUPPORTED_EVENTS, listen_for_mouse_event
from quiz_relay.relays import available_relays
from quiz_relay.relays.keyboard_led import scan_keyboard_leds


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quiz-relay")
    parser.add_argument("--config", help="Path to config.toml (default: ./config.toml)")
    sub = parser.add_subparsers(dest="command", required=True)

    solve_cmd = sub.add_parser("solve", help="Run one screenshot-to-relay cycle")
    solve_cmd.add_argument("--mode", help="Prompt mode (file stem in prompts/).")
    _add_relay_arg(solve_cmd)
    solve_cmd.add_argument("--image", help="Use this image file instead of capturing a screenshot.")

    listen = sub.add_parser("listen", help="Run solve on each mouse event")
    listen.add_argument("--mode", help="Prompt mode (file stem in prompts/).")
    _add_relay_arg(listen)
    listen.add_argument("--event", choices=sorted(SUPPORTED_EVENTS))
    listen.add_argument("--scan", action="store_true", help="Print each detected event")
    listen.add_argument("--list-events", action="store_true", help="List supported events")

    sub.add_parser("modes", help="List available prompt modes")
    sub.add_parser("relays", help="List available relay modules")
    sub.add_parser("scan-leds", help="List keyboard LED devices for [relay.keyboard_led].")

    relay_test = sub.add_parser(
        "relay-test",
        help="Send a fixed test signal (3 pulses) to the configured relay.",
    )
    _add_relay_arg(relay_test)
    return parser


def _add_relay_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--relay",
        action="append",
        default=[],
        help=(
            "Relay to dispatch to. Repeat for multiple. Available: "
            + (", ".join(available_relays()) or "(none)")
        ),
    )


def _config_path(args: argparse.Namespace) -> Path | None:
    return Path(args.config).expanduser() if args.config else None


def _require_mode(args: argparse.Namespace) -> str:
    mode = (args.mode or "").strip()
    if not mode:
        raise SystemExit("--mode is required.")
    return mode


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "solve":
            return _cmd_solve(args)
        if args.command == "listen":
            return _cmd_listen(args)
        if args.command == "modes":
            return _cmd_modes(args)
        if args.command == "relays":
            return _cmd_relays()
        if args.command == "scan-leds":
            return _cmd_scan_leds()
        if args.command == "relay-test":
            return _cmd_relay_test(args)
    except QuizRelayError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 1


def _cmd_solve(args: argparse.Namespace) -> int:
    settings = load_settings(_config_path(args))
    mode = _require_mode(args)
    image = Path(args.image).expanduser() if args.image else None
    report = run_solve(settings, mode, args.relay, image=image)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _cmd_listen(args: argparse.Namespace) -> int:
    if args.list_events:
        for name, description in SUPPORTED_EVENTS.items():
            print(f"{name}: {description}")
        return 0

    settings = load_settings(_config_path(args))

    if args.scan:
        print("Scanning mouse events. Stop with Ctrl+C.", flush=True)
        listen_for_mouse_event("middle-click", lambda _event: None, scan=True)
        return 0

    mode = _require_mode(args)
    validate_mode(settings, mode)
    event_name = args.event or settings.mouse_event
    relay_names: list[str] = args.relay

    def on_event(event) -> None:
        report = run_solve(settings, mode, relay_names, event_name=event.name)
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)

    relay_hint = ",".join(relay_names) if relay_names else "(none)"
    print(f"Listening for {event_name} (mode={mode}, relays={relay_hint})", flush=True)
    listen_for_mouse_event(event_name, on_event)
    return 0


def _cmd_modes(args: argparse.Namespace) -> int:
    settings = load_settings(_config_path(args))
    modes = available_modes(settings.prompts_dir)
    if not modes:
        print(f"No modes found in {settings.prompts_dir}/", file=sys.stderr)
        return 1
    for mode in modes:
        print(mode)
    return 0


def _cmd_relays() -> int:
    relays = available_relays()
    if not relays:
        print("No relay modules found.", file=sys.stderr)
        return 1
    for name in relays:
        print(name)
    return 0


def _cmd_scan_leds() -> int:
    devices = scan_keyboard_leds()
    if not devices:
        print("No keyboard lock LEDs found under /sys/class/leds.", file=sys.stderr)
        return 1

    print("Keyboard lock LEDs:")
    device_width = max(len("device"), *(len(d.device) for d in devices))
    lock_width = max(len("lock"), *(len(d.lock) for d in devices))
    writable_width = len("writable")
    header = (
        f"{'device':<{device_width}}  "
        f"{'lock':<{lock_width}}  "
        f"{'writable':<{writable_width}}  "
        "brightness"
    )
    print(header)
    print("-" * len(header))
    for device in devices:
        writable = "yes" if device.writable else "no"
        brightness = f"{device.brightness}/{device.max_brightness}"
        print(
            f"{device.device:<{device_width}}  "
            f"{device.lock:<{lock_width}}  "
            f"{writable:<{writable_width}}  "
            f"{brightness}"
        )
        print(f'  config: device = "{device.device}"')
        print(f"  path:   {device.brightness_path}")
        print(f"  target: {device.target_path}")
    return 0


def _cmd_relay_test(args: argparse.Namespace) -> int:
    if not args.relay:
        raise SystemExit("--relay is required (e.g. --relay http or --relay keyboard_led).")
    settings = load_settings(_config_path(args))
    report, exit_code = run_relay_test(settings, args.relay)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
