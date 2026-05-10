from __future__ import annotations

import os
import platform
import threading
from dataclasses import dataclass
from typing import Callable

from quiz_relay.errors import TriggerError


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
    """Convert a pynput button object into a configured event name."""
    name = getattr(button, "name", str(button)).lower()
    return BUTTON_EVENT_NAMES.get(name, f"{name}-click")


def scroll_event_name(dx: int, dy: int) -> str | None:
    """Convert scroll deltas into a configured event name."""
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
    """Fail early when the current desktop session cannot expose global mouse events."""
    if platform.system().lower() != "linux":
        return

    session_type = os.getenv("XDG_SESSION_TYPE", "").lower()
    display = os.getenv("DISPLAY")
    wayland_display = os.getenv("WAYLAND_DISPLAY")

    if session_type == "wayland" or wayland_display:
        raise TriggerError(
            "Global mouse events are currently supported through pynput on X11. "
            "Wayland sessions usually block this access."
        )
    if not display:
        raise TriggerError("No X11 display found. The DISPLAY environment variable is missing.")


def listen_for_mouse_event(event_name: str, callback: Callable[[MouseEvent], None], scan: bool = False) -> None:
    """Listen for mouse events and run the callback for matching events."""
    if event_name not in SUPPORTED_EVENTS and not scan:
        raise TriggerError(f"Unknown mouse event: {event_name}")
    ensure_mouse_capture_context()
    try:
        from pynput import mouse
    except ImportError as exc:
        raise TriggerError("The Python package 'pynput' is not installed.") from exc

    lock = threading.Lock()

    def emit(event: MouseEvent) -> None:
        if scan:
            _print_scanned_event(event)
            return
        if event.name != event_name:
            return
        _run_callback_exclusively(lock, callback, event)

    def on_click(x: int, y: int, button: object, pressed: bool) -> None:
        if pressed:
            emit(MouseEvent(button_event_name(button), x, y))

    def on_scroll(x: int, y: int, dx: int, dy: int) -> None:
        name = scroll_event_name(dx, dy)
        if name:
            emit(MouseEvent(name, x, y))

    with mouse.Listener(on_click=on_click, on_scroll=on_scroll) as listener:
        listener.join()


def _print_scanned_event(event: MouseEvent) -> None:
    print(event.name, flush=True)


def _run_callback_exclusively(lock, callback: Callable[[MouseEvent], None], event: MouseEvent) -> None:
    if not lock.acquire(blocking=False):
        print("A run is already active. Ignoring event.", flush=True)
        return
    try:
        callback(event)
    finally:
        lock.release()
