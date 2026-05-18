from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Option:
    id: str
    text: str


@dataclass(frozen=True)
class QuestionSolution:
    question: int
    question_text: str
    options: list[Option]
    answers: list[str]


@dataclass(frozen=True)
class Solution:
    explanation: str
    confidence: float
    questions: list[QuestionSolution] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_raw(cls, data: dict[str, Any]) -> "Solution":
        questions: list[QuestionSolution] = []
        for raw in data.get("answers", []):
            if not isinstance(raw, dict):
                continue
            options = [
                Option(id=str(opt.get("id", "")).strip(), text=str(opt.get("text", "")))
                for opt in raw.get("options", [])
                if isinstance(opt, dict)
            ]
            answers = [a.strip().upper() for a in raw.get("answers", []) if isinstance(a, str)]
            questions.append(
                QuestionSolution(
                    question=int(raw.get("question", len(questions) + 1)),
                    question_text=str(raw.get("question_text", "")),
                    options=options,
                    answers=answers,
                )
            )
        return cls(
            explanation=str(data.get("explanation", "")),
            confidence=float(data.get("confidence", 0.0) or 0.0),
            questions=questions,
        )

    @property
    def all_answer_ids(self) -> list[str]:
        return [a for q in self.questions for a in q.answers]
