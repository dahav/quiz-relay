from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MonitorInfo:
    index: int
    left: int
    top: int
    width: int
    height: int

    def describe(self) -> str:
        return f"{self.index}: {self.width}x{self.height} @ {self.left},{self.top}"


@dataclass(frozen=True)
class ScreenshotResult:
    path: str
    mime_type: str = "image/png"
    width: int | None = None
    height: int | None = None
    size_bytes: int | None = None
