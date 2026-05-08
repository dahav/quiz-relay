from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Esp32SendResult:
    sent: bool
    status_code: int | None
    response_body: str | None
    duration_ms: int
    error: str | None = None

    @classmethod
    def disabled(cls) -> "Esp32SendResult":
        return cls(sent=False, status_code=None, response_body=None, duration_ms=0, error="disabled")
