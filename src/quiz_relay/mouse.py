from __future__ import annotations

import os
import platform
import sys
import threading
from dataclasses import dataclass
from typing import Callable

SUPPORTED_EVENTS = {
    "left-click": "Left click",
    "right-click": "Right click",
    "middle-click": "Middle click",
    "button4-click": "Side button 1 / button 4",
    "button5-click": "Side button 2 / button 5",
    "scroll-up": "Mouse wheel up",
    "scroll-down": "Mouse wheel down",
    "scroll-left": "Horizontal scroll left",
    "scroll-right": "Horizontal scroll right",
}

_BUTTON_NAMES = {
    "left": "left-click", "right": "right-click", "middle": "middle-click",
    "x1": "button4-click", "x2": "button5-click",
    "button8": "button4-click", "button9": "button5-click",
}


@dataclass(frozen=True)
class MouseEvent:
    name: str
    x: int
    y: int


def listen_for_mouse_event(event_name: str, callback: Callable[[MouseEvent], None], scan: bool = False) -> None:
    if event_name not in SUPPORTED_EVENTS and not scan:
        raise SystemExit(f"Unknown mouse event: {event_name}")
    if platform.system().lower() == "linux":
        if os.getenv("WAYLAND_DISPLAY") or os.getenv("XDG_SESSION_TYPE", "").lower() == "wayland":
            raise SystemExit("Global mouse events are supported on X11 only. Wayland blocks this access.")
        if not os.getenv("DISPLAY"):
            raise SystemExit("No X11 display found. DISPLAY is missing.")
    from pynput import mouse

    lock = threading.Lock()

    def emit(event: MouseEvent) -> None:
        if scan:
            print(event.name, flush=True)
            return
        if event.name != event_name:
            return
        if not lock.acquire(blocking=False):
            print("A run is already active. Ignoring event.", flush=True)
            return
        try:
            callback(event)
        except SystemExit as exc:
            print(f"run failed: {exc}", file=sys.stderr, flush=True)
        except Exception as exc:
            print(f"run failed: {exc}", file=sys.stderr, flush=True)
        finally:
            lock.release()

    def on_click(x: int, y: int, button: object, pressed: bool) -> None:
        if not pressed:
            return
        raw = getattr(button, "name", str(button)).lower()
        emit(MouseEvent(_BUTTON_NAMES.get(raw, f"{raw}-click"), x, y))

    def on_scroll(x: int, y: int, dx: int, dy: int) -> None:
        if abs(dy) >= abs(dx):
            name = "scroll-up" if dy > 0 else "scroll-down" if dy < 0 else None
        else:
            name = "scroll-right" if dx > 0 else "scroll-left" if dx < 0 else None
        if name:
            emit(MouseEvent(name, x, y))

    with mouse.Listener(on_click=on_click, on_scroll=on_scroll) as listener:
        listener.join()
