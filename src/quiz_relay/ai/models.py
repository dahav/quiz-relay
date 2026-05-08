from __future__ import annotations

from dataclasses import dataclass


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
