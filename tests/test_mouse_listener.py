import pytest

from quiz_relay.errors import TriggerError
from quiz_relay.triggers.mouse_listener import button_event_name, ensure_mouse_capture_context, scroll_event_name


class Button:
    def __init__(self, name):
        self.name = name


def test_button_event_mapping():
    assert button_event_name(Button("middle")) == "middle-click"
    assert button_event_name(Button("x1")) == "button4-click"


def test_scroll_event_mapping():
    assert scroll_event_name(0, 1) == "scroll-up"
    assert scroll_event_name(0, -1) == "scroll-down"
    assert scroll_event_name(1, 0) == "scroll-right"
    assert scroll_event_name(-1, 0) == "scroll-left"


def test_mouse_capture_context_rejects_wayland(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")

    with pytest.raises(TriggerError, match="nur unter X11"):
        ensure_mouse_capture_context()


def test_mouse_capture_context_requires_display(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)

    with pytest.raises(TriggerError, match="DISPLAY fehlt"):
        ensure_mouse_capture_context()

