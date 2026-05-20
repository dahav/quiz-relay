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
