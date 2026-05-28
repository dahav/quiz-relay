from __future__ import annotations


class QuizRelayError(Exception):
    """Base class for expected application errors."""


class ConfigError(QuizRelayError):
    pass


class UnknownModeError(QuizRelayError):
    pass


class InvalidImageError(QuizRelayError):
    pass


class AiResponseError(QuizRelayError):
    pass


def error_status(exc: QuizRelayError) -> int:
    if isinstance(exc, UnknownModeError):
        return 404
    if isinstance(exc, InvalidImageError):
        return 400
    if isinstance(exc, ConfigError):
        return 500
    if isinstance(exc, AiResponseError):
        return 502
    return 500
