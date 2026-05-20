from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from quiz_relay.config import Settings, load_settings
from quiz_relay.core import available_modes, load_mode, solve
from quiz_relay.errors import QuizRelayError
from quiz_relay.mouse import SUPPORTED_EVENTS, MouseEvent, listen_for_mouse_event
from quiz_relay.relays import available_relays, build_relay
from quiz_relay.relays.keyboard_led import scan_keyboard_leds
from quiz_relay.solution import answers_to_pulses

RELAY_TEST_PULSES: list[int] = [3]


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


def _dispatch_relays(names: list[str], settings: Settings, pulses: list[int]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    if not names:
        print("[relay] none selected (pass --relay <name> to dispatch)", flush=True)
        return results
    print(f"[relay] dispatching to: {', '.join(names)} pulses={pulses}", flush=True)
    for name in names:
        print(f"[relay:{name}] sending...", flush=True)
        try:
            relay = build_relay(name, settings.relays.get(name, {}))
            result = relay.send(pulses)
        except (SystemExit, Exception) as exc:
            result = {"sent": False, "error": str(exc)}
        results[name] = result
        status = "OK" if result.get("sent") else "FAILED"
        print(f"[relay:{name}] {status} {result}", flush=True)
    return results


def _run_once(
    settings: Settings,
    mode: str,
    relay_names: list[str],
    image: Path | None = None,
    event: MouseEvent | None = None,
) -> dict[str, Any]:
    solution, source, source_key = solve(settings, mode, image=image)
    pulses = answers_to_pulses(solution.all_answer_ids)
    relay_results = _dispatch_relays(relay_names, settings, pulses)
    report: dict[str, Any] = {"mode": mode, source_key: str(source), "solution": solution.to_dict()}
    if event is not None:
        report = {"event": event.name, **report}
    if relay_results:
        report["relays"] = relay_results
    return report


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
    image = Path(args.image).expanduser() if args.image else None
    mode = _require_mode(args)
    report = _run_once(settings, mode, args.relay, image=image)
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
    load_mode(settings.prompts_dir, mode)
    event_name = args.event or settings.mouse_event
    relay_names: list[str] = args.relay

    def on_event(event: MouseEvent) -> None:
        report = _run_once(settings, mode, relay_names, event=event)
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
        print(f"  config: device = \"{device.device}\"")
        print(f"  path:   {device.brightness_path}")
        print(f"  target: {device.target_path}")
    return 0


def _cmd_relay_test(args: argparse.Namespace) -> int:
    if not args.relay:
        raise SystemExit("--relay is required (e.g. --relay http or --relay keyboard_led).")
    settings = load_settings(_config_path(args))
    relay_results = _dispatch_relays(args.relay, settings, RELAY_TEST_PULSES)
    print(json.dumps({"test_pulses": RELAY_TEST_PULSES, "relays": relay_results}, ensure_ascii=False, indent=2))
    return 0 if all(r.get("sent") for r in relay_results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
