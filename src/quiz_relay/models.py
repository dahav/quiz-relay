from __future__ import annotations

import getpass
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from quiz_relay.errors import QuizRelayError


def local_now() -> datetime:
    return datetime.now().astimezone()


def _task_timestamp(dt: datetime) -> str:
    local_dt = dt.astimezone()
    return local_dt.strftime("%Y-%m-%dT%H-%M-%S.%f")[:-3] + local_dt.strftime("%z")


def format_timestamp(dt: datetime) -> str:
    return dt.astimezone().isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class RunContext:
    task_id: str
    source: str
    started_at: datetime
    host: str | None
    user: str | None
    config_profile: str

    @classmethod
    def create(cls, source: str, config_profile: str = "default") -> "RunContext":
        started_at = local_now()
        return cls(
            task_id=f"{_task_timestamp(started_at)}-{uuid.uuid4().hex[:4]}",
            source=source,
            started_at=started_at,
            host=socket.gethostname(),
            user=getpass.getuser(),
            config_profile=config_profile,
        )

    def started_iso(self) -> str:
        return format_timestamp(self.started_at)


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


@dataclass(frozen=True)
class QuestionAnswer:
    question: int
    answers: list[str]


@dataclass(frozen=True)
class AiSolution:
    explanation: str
    answers: list[QuestionAnswer]
    confidence: float | None = None
    raw_response: str | None = None


@dataclass(frozen=True)
class AiRawResponse:
    text: str
    provider: str
    model: str


@dataclass(frozen=True)
class RelaySendResult:
    sent: bool
    status_code: int | None
    response_body: str | None
    duration_ms: int
    error: str | None = None

    @classmethod
    def disabled(cls) -> "RelaySendResult":
        return cls(sent=False, status_code=None, response_body=None, duration_ms=0, error="disabled")


@dataclass(frozen=True)
class ErrorInfo:
    stage: str
    error_type: str
    message: str

    @classmethod
    def from_exception(cls, exc: QuizRelayError) -> "ErrorInfo":
        return cls(stage=exc.stage, error_type=exc.__class__.__name__, message=str(exc))


@dataclass(frozen=True)
class RunResult:
    context: RunContext
    status: Literal["success", "failed", "partial", "locked"]
    finished_at: datetime
    screenshot: ScreenshotResult | None = None
    solution: AiSolution | None = None
    relay_result: RelaySendResult | None = None
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
        relay_result: RelaySendResult,
    ) -> "RunResult":
        return cls(context, "success", local_now(), screenshot, solution, relay_result)

    @classmethod
    def partial(
        cls,
        context: RunContext,
        screenshot: ScreenshotResult,
        solution: AiSolution,
        relay_result: RelaySendResult,
    ) -> "RunResult":
        return cls(context, "partial", local_now(), screenshot, solution, relay_result)

    @classmethod
    def failed(
        cls,
        context: RunContext,
        exc: QuizRelayError,
        screenshot: ScreenshotResult | None = None,
    ) -> "RunResult":
        return cls(context, "failed", local_now(), screenshot=screenshot, error=ErrorInfo.from_exception(exc))

    @classmethod
    def locked(cls, context: RunContext, exc: QuizRelayError) -> "RunResult":
        return cls(context, "locked", local_now(), error=ErrorInfo.from_exception(exc))
