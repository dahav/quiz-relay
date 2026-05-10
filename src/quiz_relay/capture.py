from __future__ import annotations

import os
import platform
import time
from pathlib import Path

from quiz_relay.config import Settings
from quiz_relay.errors import ScreenshotCaptureError
from quiz_relay.models import MonitorInfo, RunContext, ScreenshotResult


def screenshot_path(settings: Settings, context: RunContext) -> Path:
    screenshots_dir = settings.app.runtime_directory / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    return screenshots_dir / f"{context.task_id}.png"


def screenshot_from_file(path: Path) -> ScreenshotResult:
    image_path = path.expanduser().resolve()
    if not image_path.is_file():
        raise ScreenshotCaptureError(f"Test image not found: {image_path}")
    suffix = image_path.suffix.lower()
    mime_type = "image/png" if suffix == ".png" else "image/jpeg" if suffix in {".jpg", ".jpeg"} else None
    if mime_type is None:
        raise ScreenshotCaptureError("Test image must be PNG or JPEG.")
    return ScreenshotResult(path=str(image_path), mime_type=mime_type, size_bytes=image_path.stat().st_size)


def capture_screenshot(settings: Settings, context: RunContext) -> ScreenshotResult:
    _ensure_desktop_context()
    if settings.screenshot.delay_ms > 0:
        time.sleep(settings.screenshot.delay_ms / 1000)

    mss = _require_mss()
    output_path = screenshot_path(settings, context)
    try:
        with mss.MSS() as sct:
            monitor_index = settings.screenshot.monitor
            if monitor_index < 1 or monitor_index >= len(sct.monitors):
                raise ScreenshotCaptureError(f"Monitor {monitor_index} is not available.")
            screenshot = sct.grab(sct.monitors[monitor_index])
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


def _ensure_desktop_context() -> None:
    if platform.system().lower() != "linux":
        return
    if os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"):
        return
    raise ScreenshotCaptureError("No desktop display found. DISPLAY or WAYLAND_DISPLAY is missing.")
