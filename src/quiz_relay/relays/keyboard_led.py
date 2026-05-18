from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quiz_relay.relays.base import Relay

LEDS_ROOT = Path("/sys/class/leds")
LOCK_LED_SUFFIXES = ("::capslock", "::numlock", "::scrolllock")
LOCK_LED_RANK = {
    "::capslock": 0,
    "::numlock": 1,
    "::scrolllock": 2,
}


@dataclass(frozen=True)
class KeyboardLedDevice:
    device: str
    lock: str
    brightness_path: Path
    target_path: Path
    brightness: str
    max_brightness: str
    writable: bool


def _lock_led_rank(device: str) -> tuple[int, str]:
    for suffix, rank in LOCK_LED_RANK.items():
        if device.endswith(suffix):
            return rank, device
    return len(LOCK_LED_RANK), device


def _available_lock_leds() -> list[str]:
    try:
        entries = list(LEDS_ROOT.iterdir())
    except OSError:
        return []

    devices: list[str] = []
    for entry in entries:
        if entry.name.endswith(LOCK_LED_SUFFIXES) and (entry / "brightness").exists():
            devices.append(entry.name)
    return sorted(devices, key=_lock_led_rank)


def _read_text(path: Path, default: str = "?") -> str:
    try:
        return path.read_text().strip() or default
    except OSError:
        return default


def _lock_name(device: str) -> str:
    return device.rsplit("::", maxsplit=1)[-1]


def _is_writable(path: Path) -> bool:
    try:
        return os.access(path, os.W_OK)
    except OSError:
        return False


def scan_keyboard_leds() -> list[KeyboardLedDevice]:
    devices: list[KeyboardLedDevice] = []
    for device in _available_lock_leds():
        led_path = LEDS_ROOT / device
        brightness_path = led_path / "brightness"
        try:
            target_path = led_path.resolve(strict=False)
        except OSError:
            target_path = led_path
        devices.append(
            KeyboardLedDevice(
                device=device,
                lock=_lock_name(device),
                brightness_path=brightness_path,
                target_path=target_path,
                brightness=_read_text(brightness_path),
                max_brightness=_read_text(led_path / "max_brightness", default="1"),
                writable=_is_writable(brightness_path),
            )
        )
    return devices


@dataclass(frozen=True)
class KeyboardLedRelay(Relay):
    name = "keyboard_led"

    device: str
    on: int
    off: int
    pause: int
    max_pulses: int

    @classmethod
    def from_config(cls, section: dict[str, Any]) -> "KeyboardLedRelay":
        device = str(section.get("device", "")).strip()
        if not device or device.lower() in {"auto", "default"}:
            raise SystemExit(
                "[relay.keyboard_led] device is required. Run `quiz-relay scan-leds` "
                "and paste one config value, e.g. device = \"input4::capslock\"."
            )
        return cls(
            device=device,
            on=int(section.get("on", 300)),
            off=int(section.get("off", 200)),
            pause=int(section.get("pause", 800)),
            max_pulses=int(section.get("max_pulses", 9)),
        )

    def _resolve_brightness_path(self) -> tuple[Path | None, str | None, str | None]:
        path = LEDS_ROOT / self.device / "brightness"
        if path.exists():
            return path, self.device, None
        return None, None, f"LED device not found: {path}. Run `quiz-relay scan-leds` and update config.toml."

    def send(self, pulses: list[int]) -> dict[str, Any]:
        path, device, error = self._resolve_brightness_path()
        if path is None or device is None:
            msg = error or "LED device not found"
            print(f"relay[keyboard_led] error: {msg}", file=sys.stderr, flush=True)
            return {"sent": False, "error": msg}

        if not pulses:
            print("relay[keyboard_led] no pulses to send", file=sys.stderr, flush=True)
            return {"sent": False, "error": "no pulses"}

        try:
            max_brightness = int((path.parent / "max_brightness").read_text().strip() or "1")
        except OSError:
            max_brightness = 1
        on_s = self.on / 1000.0
        off_s = self.off / 1000.0
        pause_s = self.pause / 1000.0

        print(f"relay[keyboard_led] device={device} pulses={pulses}", file=sys.stderr, flush=True)
        try:
            for i, count in enumerate(pulses):
                if i > 0:
                    time.sleep(pause_s)
                for j in range(min(count, self.max_pulses)):
                    if j > 0:
                        time.sleep(off_s)
                    path.write_text(f"{max_brightness}\n")
                    time.sleep(on_s)
                    path.write_text("0\n")
        except PermissionError as exc:
            msg = f"permission denied on {path} (install udev rule, see README)"
            print(f"relay[keyboard_led] error: {msg}", file=sys.stderr, flush=True)
            return {"sent": False, "error": msg, "detail": str(exc)}
        except OSError as exc:
            print(f"relay[keyboard_led] error: {exc}", file=sys.stderr, flush=True)
            return {"sent": False, "error": str(exc)}
        return {"sent": True, "pulses": pulses, "device": device}
