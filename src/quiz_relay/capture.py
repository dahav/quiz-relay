from __future__ import annotations

import os
import platform
import time
from pathlib import Path

from quiz_relay.config import Settings
from quiz_relay.errors import ScreenshotCaptureError
from quiz_relay.models import MonitorInfo, RunContext, ScreenshotResult


def screenshot_path(settings: Settings, context: RunContext) -> Path:
    """Return the runtime path used for a captured screenshot."""
    screenshots_dir = settings.app.runtime_directory / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    return screenshots_dir / f"{context.task_id}.png"


def screenshot_from_file(path: Path) -> ScreenshotResult:
    """Wrap an existing PNG or JPEG file as a screenshot result for test runs."""
    image_path = path.expanduser().resolve()
    if not image_path.is_file():
        raise ScreenshotCaptureError(f"Test image not found: {image_path}")
    mime_type = _image_mime_type(image_path)
    if mime_type is None:
        raise ScreenshotCaptureError("Test image must be PNG or JPEG.")
    return ScreenshotResult(path=str(image_path), mime_type=mime_type, size_bytes=image_path.stat().st_size)


def capture_screenshot(settings: Settings, context: RunContext) -> ScreenshotResult:
    """Capture the configured monitor and save it under the runtime directory."""
    _ensure_desktop_context()
    if settings.screenshot.delay_ms > 0:
        time.sleep(settings.screenshot.delay_ms / 1000)

    mss = _require_mss()
    output_path = screenshot_path(settings, context)
    try:
        with mss.MSS() as sct:
            monitor = _selected_monitor(sct.monitors, settings.screenshot.monitor)
            screenshot = sct.grab(monitor)
            mss.tools.to_png(screenshot.rgb, screenshot.size, output=str(output_path))
            return ScreenshotResult(
                path=str(output_path),
                width=int(screenshot.width),
                height=int(screenshot.height),
                size_bytes=output_path.stat().st_size,
            )
    except ScreenshotCaptureError:
        raise
    except Exception as exc:
        raise ScreenshotCaptureError(f"Screenshot capture failed: {exc}") from exc


def list_monitors(settings: Settings) -> list[MonitorInfo]:
    """Return monitor geometry reported by the screenshot backend."""
    _ensure_desktop_context()
    mss = _require_mss()
    try:
        with mss.MSS() as sct:
            return [
                MonitorInfo(
                    index=index,
                    left=int(monitor["left"]),
                    top=int(monitor["top"]),
                    width=int(monitor["width"]),
                    height=int(monitor["height"]),
                )
                for index, monitor in enumerate(sct.monitors[1:], start=1)
            ]
    except Exception as exc:
        raise ScreenshotCaptureError(f"Could not list monitors: {exc}") from exc


def _require_mss():
    try:
        import mss
        import mss.tools
    except ImportError as exc:
        raise ScreenshotCaptureError("The Python package 'mss' is not installed.") from exc
    return mss


def _image_mime_type(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    return None


def _selected_monitor(monitors: list[dict], monitor_index: int) -> dict:
    if monitor_index < 1 or monitor_index >= len(monitors):
        raise ScreenshotCaptureError(f"Monitor {monitor_index} is not available.")
    return monitors[monitor_index]


def _ensure_desktop_context() -> None:
    if platform.system().lower() != "linux":
        return
    if os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"):
        return
    raise ScreenshotCaptureError("No desktop display found. DISPLAY or WAYLAND_DISPLAY is missing.")
