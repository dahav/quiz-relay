from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Callable

from quiz_relay.errors import TriggerError


SUPPORTED_EVENTS = {
    "left-click": "Linksklick",
    "right-click": "Rechtsklick",
    "middle-click": "Mittelklick",
    "button4-click": "Seitentaste 1 / Button 4",
    "button5-click": "Seitentaste 2 / Button 5",
    "scroll-up": "Mausrad nach oben",
    "scroll-down": "Mausrad nach unten",
    "scroll-left": "Horizontales Scrollen nach links",
    "scroll-right": "Horizontales Scrollen nach rechts",
}


@dataclass(frozen=True)
class MouseEvent:
    name: str
    x: int
    y: int


def button_event_name(button: object) -> str:
    name = getattr(button, "name", str(button)).lower()
    mapping = {
        "left": "left-click",
        "right": "right-click",
        "middle": "middle-click",
        "x1": "button4-click",
        "x2": "button5-click",
        "button8": "button4-click",
        "button9": "button5-click",
    }
    return mapping.get(name, f"{name}-click")


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
    session_type = os.getenv("XDG_SESSION_TYPE", "").lower()
    display = os.getenv("DISPLAY")
    wayland_display = os.getenv("WAYLAND_DISPLAY")

    if session_type == "wayland" or wayland_display:
        raise TriggerError(
            "Globale Mausevents werden derzeit nur unter X11 unterstuetzt. "
            "Bitte in eine X11/Xorg-Sitzung wechseln und den Befehl erneut ausfuehren."
        )
    if not display:
        raise TriggerError("Kein X11-Display gefunden. Die Umgebungsvariable DISPLAY fehlt.")


class MouseEventListener:
    def __init__(self, event_name: str, callback: Callable[[MouseEvent], None], scan: bool = False) -> None:
        if event_name not in SUPPORTED_EVENTS and not scan:
            raise TriggerError(f"Unbekanntes Mouse-Event: {event_name}")
        self.event_name = event_name
        self.callback = callback
        self.scan = scan
        self._lock = threading.Lock()

    def start(self) -> None:
        ensure_mouse_capture_context()
        try:
            from pynput import mouse
        except ImportError as exc:
            raise TriggerError("Das Python-Paket 'pynput' ist nicht installiert.") from exc

        def emit(event: MouseEvent) -> None:
            if self.scan:
                print(event.name, flush=True)
                return
            if event.name != self.event_name:
                return
            if not self._lock.acquire(blocking=False):
                print("Pipeline laeuft bereits. Event wird ignoriert.", flush=True)
                return
            try:
                self.callback(event)
            finally:
                self._lock.release()

        def on_click(x: int, y: int, button: object, pressed: bool) -> None:
            if pressed:
                emit(MouseEvent(button_event_name(button), x, y))

        def on_scroll(x: int, y: int, dx: int, dy: int) -> None:
            event_name = scroll_event_name(dx, dy)
            if event_name:
                emit(MouseEvent(event_name, x, y))

        with mouse.Listener(on_click=on_click, on_scroll=on_scroll) as listener:
            listener.join()
