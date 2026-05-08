from __future__ import annotations

from pathlib import Path

from quiz_relay.errors import ScreenshotCaptureError
from quiz_relay.pipeline.run_context import RunContext
from quiz_relay.screenshot.monitor_models import MonitorInfo, ScreenshotResult
from quiz_relay.screenshot.screenshot_store import ScreenshotStore


class ScreenshotService:
    def __init__(self, backend, store: ScreenshotStore) -> None:
        self.backend = backend
        self.store = store

    def capture(self, context: RunContext) -> ScreenshotResult:
        return self.backend.capture(self.store.path_for(context))

    def from_file(self, path: Path) -> ScreenshotResult:
        image_path = path.expanduser().resolve()
        if not image_path.is_file():
            raise ScreenshotCaptureError(f"Testbild nicht gefunden: {image_path}")
        suffix = image_path.suffix.lower()
        mime_type = "image/png" if suffix == ".png" else "image/jpeg" if suffix in {".jpg", ".jpeg"} else None
        if mime_type is None:
            raise ScreenshotCaptureError("Testbild muss PNG oder JPEG sein.")
        return ScreenshotResult(path=str(image_path), mime_type=mime_type, size_bytes=image_path.stat().st_size)

    def list_monitors(self) -> list[MonitorInfo]:
        return self.backend.list_monitors()
