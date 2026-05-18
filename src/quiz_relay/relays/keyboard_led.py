from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quiz_relay.relays.base import Relay
from quiz_relay.solution import Solution

PULSE = {letter: i for i, letter in enumerate("ABCDEFGHI", 1)} | {str(i): i for i in range(1, 10)}

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

    def _brightness_path(self) -> Path:
        return LEDS_ROOT / self.device / "brightness"

    def _max_brightness(self, path: Path) -> int:
        try:
            return int((path.parent / "max_brightness").read_text().strip() or "1")
        except OSError:
            return 1

    def _write(self, path: Path, value: int) -> None:
        path.write_text(f"{value}\n")

    def send(self, solution: Solution) -> dict[str, Any]:
        path = self._brightness_path()
        if not path.exists():
            msg = f"LED device not found: {path}"
            print(f"relay[keyboard_led] error: {msg}", file=sys.stderr, flush=True)
            return {"sent": False, "error": msg}

        pulse_counts = [PULSE[a] for a in solution.all_answer_ids if a in PULSE]
        if not pulse_counts:
            print("relay[keyboard_led] no answers to signal", file=sys.stderr, flush=True)
            return {"sent": False, "error": "no answers"}

        on_value = self._max_brightness(path)
        on_s = self.on / 1000.0
        off_s = self.off / 1000.0
        pause_s = self.pause / 1000.0

        print(
            f"relay[keyboard_led] device={self.device} pulses={pulse_counts}",
            file=sys.stderr,
            flush=True,
        )
        try:
            for i, count in enumerate(pulse_counts):
                if i > 0:
                    time.sleep(pause_s)
                for j in range(min(count, self.max_pulses)):
                    if j > 0:
                        time.sleep(off_s)
                    self._write(path, on_value)
                    time.sleep(on_s)
                    self._write(path, 0)
        except PermissionError as exc:
            msg = f"permission denied on {path} (install udev rule, see README)"
            print(f"relay[keyboard_led] error: {msg}", file=sys.stderr, flush=True)
            return {"sent": False, "error": msg, "detail": str(exc)}
        except OSError as exc:
            print(f"relay[keyboard_led] error: {exc}", file=sys.stderr, flush=True)
            return {"sent": False, "error": str(exc)}
        return {"sent": True, "pulses": pulse_counts}
