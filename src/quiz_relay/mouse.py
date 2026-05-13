from __future__ import annotations

import os
import platform
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

BUTTON_EVENT_NAMES = {
    "left": "left-click",
    "right": "right-click",
    "middle": "middle-click",
    "x1": "button4-click",
    "x2": "button5-click",
    "button8": "button4-click",
    "button9": "button5-click",
}


@dataclass(frozen=True)
class MouseEvent:
    name: str
    x: int
    y: int


def button_event_name(button: object) -> str:
    name = getattr(button, "name", str(button)).lower()
    return BUTTON_EVENT_NAMES.get(name, f"{name}-click")


def scroll_event_name(dx: int, dy: int) -> str | None:
    if abs(dy) >= abs(dx) and dy > 0:
        return "scroll-up"
    if abs(dy) >= abs(dx) and dy < 0:
        return "scroll-down"
    if dx > 0:
        return "scroll-right"
    if dx < 0:
        return "scroll-left"
    return None


def ensure_mouse_capture_context() -> None:
    if platform.system().lower() != "linux":
        return
    session_type = os.getenv("XDG_SESSION_TYPE", "").lower()
    if session_type == "wayland" or os.getenv("WAYLAND_DISPLAY"):
        raise SystemExit(
            "Global mouse events are supported on X11 only. Wayland blocks this access."
        )
    if not os.getenv("DISPLAY"):
        raise SystemExit("No X11 display found. DISPLAY is missing.")


def listen_for_mouse_event(event_name: str, callback: Callable[[MouseEvent], None], scan: bool = False) -> None:
    if event_name not in SUPPORTED_EVENTS and not scan:
        raise SystemExit(f"Unknown mouse event: {event_name}")
    ensure_mouse_capture_context()
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
        finally:
            lock.release()

    def on_click(x: int, y: int, button: object, pressed: bool) -> None:
        if pressed:
            emit(MouseEvent(button_event_name(button), x, y))

    def on_scroll(x: int, y: int, dx: int, dy: int) -> None:
        name = scroll_event_name(dx, dy)
        if name:
            emit(MouseEvent(name, x, y))

    with mouse.Listener(on_click=on_click, on_scroll=on_scroll) as listener:
        listener.join()
