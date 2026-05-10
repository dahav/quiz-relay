from __future__ import annotations


class QuizRelayError(Exception):
    stage = "unknown"
    exit_code = 1

    def __init__(self, message: str, *, stage: str | None = None) -> None:
        super().__init__(message)
        if stage is not None:
            self.stage = stage


class ConfigurationError(QuizRelayError):
    stage = "configuration"
    exit_code = 2


class TriggerError(QuizRelayError):
    stage = "trigger"
    exit_code = 1


class ScreenshotCaptureError(QuizRelayError):
    stage = "screenshot"
    exit_code = 3


class AiRequestError(QuizRelayError):
    stage = "ai_request"
    exit_code = 4


class AiTimeoutError(AiRequestError):
    pass


class AiResponseParseError(QuizRelayError):
    stage = "ai_parse"
    exit_code = 5


class SolutionValidationError(QuizRelayError):
    stage = "solution_validation"
    exit_code = 5


class HttpRelayConnectionError(QuizRelayError):
    stage = "http_relay_send"
    exit_code = 6


class HttpRelayError(HttpRelayConnectionError):
    pass


class AuditWriteError(QuizRelayError):
    stage = "audit"
    exit_code = 1


class RunAlreadyActiveError(QuizRelayError):
    stage = "trigger"
    exit_code = 7
