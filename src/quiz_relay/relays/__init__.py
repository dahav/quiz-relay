from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from quiz_relay.relays.base import Relay


def _discover() -> dict[str, type[Relay]]:
    registry: dict[str, type[Relay]] = {}
    package = __name__
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name == "base":
            continue
        module = importlib.import_module(f"{package}.{module_info.name}")
        for attr in vars(module).values():
            if (
                isinstance(attr, type)
                and issubclass(attr, Relay)
                and attr is not Relay
                and getattr(attr, "name", "")
            ):
                registry[attr.name] = attr
    return registry


REGISTRY: dict[str, type[Relay]] = _discover()


def available_relays() -> list[str]:
    return sorted(REGISTRY)


def build_relay(name: str, section: dict[str, Any]) -> Relay:
    cls = REGISTRY.get(name)
    if cls is None:
        hint = ", ".join(available_relays()) or "(none)"
        raise SystemExit(f"Unknown relay '{name}'. Available: {hint}")
    return cls.from_config(section)


__all__ = ["Relay", "REGISTRY", "available_relays", "build_relay"]
