from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quiz_relay.relays.base import Relay

LEDS_ROOT = Path("/sys/class/leds")


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
        device = section.get("device")
        if not device:
            raise SystemExit("[relay.keyboard_led] device is required (e.g. 'input3::capslock').")
        return cls(
            device=str(device),
            on=int(section.get("on", 300)),
            off=int(section.get("off", 200)),
            pause=int(section.get("pause", 800)),
            max_pulses=int(section.get("max_pulses", 9)),
        )

    def send(self, pulses: list[int]) -> dict[str, Any]:
        path = LEDS_ROOT / self.device / "brightness"
        if not path.exists():
            msg = f"LED device not found: {path}"
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

        print(f"relay[keyboard_led] device={self.device} pulses={pulses}", file=sys.stderr, flush=True)
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
        return {"sent": True, "pulses": pulses}
