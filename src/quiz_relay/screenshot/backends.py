from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Protocol

from quiz_relay.config import ScreenshotConfig
from quiz_relay.errors import ScreenshotCaptureError
from quiz_relay.screenshot.monitor_models import MonitorInfo, ScreenshotResult


class ScreenCaptureBackend(Protocol):
    def capture(self, output_path: Path) -> ScreenshotResult:
        ...

    def list_monitors(self) -> list[MonitorInfo]:
        ...


class MssScreenshotBackend:
    def __init__(self, config: ScreenshotConfig) -> None:
        self.config = config

    def _require_mss(self):
        try:
            import mss
            import mss.tools
        except ImportError as exc:
            raise ScreenshotCaptureError("Das Python-Paket 'mss' ist nicht installiert.") from exc
        return mss

    def _ensure_desktop_context(self) -> None:
        if os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"):
            return
        raise ScreenshotCaptureError("Kein Desktop-Display gefunden. DISPLAY oder WAYLAND_DISPLAY fehlt.")

    def list_monitors(self) -> list[MonitorInfo]:
        self._ensure_desktop_context()
        mss = self._require_mss()
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
            raise ScreenshotCaptureError(f"Monitore konnten nicht ermittelt werden: {exc}") from exc

    def capture(self, output_path: Path) -> ScreenshotResult:
        self._ensure_desktop_context()
        if self.config.delay_ms > 0:
            time.sleep(self.config.delay_ms / 1000)

        mss = self._require_mss()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with mss.MSS() as sct:
                monitor_index = self.config.monitor
                if monitor_index < 1 or monitor_index >= len(sct.monitors):
                    raise ScreenshotCaptureError(f"Monitor {monitor_index} ist nicht verfuegbar.")
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
            raise ScreenshotCaptureError(f"Screenshot konnte nicht erstellt werden: {exc}") from exc
