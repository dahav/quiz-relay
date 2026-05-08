from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from quiz_relay.ai.models import AiSolution
from quiz_relay.esp32.models import Esp32SendResult
from quiz_relay.errors import QuizRelayError
from quiz_relay.pipeline.run_context import RunContext
from quiz_relay.screenshot.monitor_models import ScreenshotResult


@dataclass(frozen=True)
class ErrorInfo:
    stage: str
    error_type: str
    message: str

    @classmethod
    def from_exception(cls, exc: QuizRelayError) -> "ErrorInfo":
        return cls(stage=exc.stage, error_type=exc.__class__.__name__, message=str(exc))


@dataclass(frozen=True)
class PipelineResult:
    context: RunContext
    status: Literal["success", "failed", "partial", "locked"]
    finished_at: datetime
    screenshot: ScreenshotResult | None = None
    solution: AiSolution | None = None
    esp32_result: Esp32SendResult | None = None
    error: ErrorInfo | None = None

    @property
    def duration_ms(self) -> int:
        return int((self.finished_at - self.context.started_at).total_seconds() * 1000)

    @classmethod
    def success(
        cls,
        context: RunContext,
        screenshot: ScreenshotResult,
        solution: AiSolution,
        esp32_result: Esp32SendResult,
    ) -> "PipelineResult":
        return cls(context, "success", datetime.now(UTC), screenshot, solution, esp32_result)

    @classmethod
    def partial(
        cls,
        context: RunContext,
        screenshot: ScreenshotResult,
        solution: AiSolution,
        esp32_result: Esp32SendResult,
    ) -> "PipelineResult":
        return cls(context, "partial", datetime.now(UTC), screenshot, solution, esp32_result)

    @classmethod
    def failed(
        cls,
        context: RunContext,
        exc: QuizRelayError,
        screenshot: ScreenshotResult | None = None,
    ) -> "PipelineResult":
        return cls(context, "failed", datetime.now(UTC), screenshot=screenshot, error=ErrorInfo.from_exception(exc))

    @classmethod
    def locked(cls, context: RunContext, exc: QuizRelayError) -> "PipelineResult":
        return cls(context, "locked", datetime.now(UTC), error=ErrorInfo.from_exception(exc))
