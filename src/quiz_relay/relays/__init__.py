from __future__ import annotations

from typing import Any

from quiz_relay.relays.base import Relay
from quiz_relay.relays.http import HttpRelay
from quiz_relay.relays.keyboard_led import KeyboardLedRelay

REGISTRY: dict[str, type[Relay]] = {
    HttpRelay.name: HttpRelay,
    KeyboardLedRelay.name: KeyboardLedRelay,
}


def available_relays() -> list[str]:
    return sorted(REGISTRY)


def build_relay(name: str, section: dict[str, Any]) -> Relay:
    cls = REGISTRY.get(name)
    if cls is None:
        hint = ", ".join(available_relays()) or "(none)"
        raise SystemExit(f"Unknown relay '{name}'. Available: {hint}")
    return cls.from_config(section)


__all__ = ["Relay", "REGISTRY", "available_relays", "build_relay"]
