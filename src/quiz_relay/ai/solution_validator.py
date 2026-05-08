from __future__ import annotations

from quiz_relay.ai.models import AiSolution, QuestionAnswer
from quiz_relay.errors import SolutionValidationError


class SolutionValidator:
    def __init__(self, allowed_answers: set[str] | None = None) -> None:
        self.allowed_answers = allowed_answers or set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    def validate(self, solution: AiSolution) -> AiSolution:
        if solution.confidence is not None and not 0 <= solution.confidence <= 1:
            raise SolutionValidationError("confidence muss zwischen 0 und 1 liegen.")

        normalized: list[QuestionAnswer] = []
        for item in solution.answers:
            if item.question < 1:
                raise SolutionValidationError("question muss groesser oder gleich 1 sein.")
            answers = []
            seen = set()
            for answer in item.answers:
                value = answer.strip().upper()
                if not value:
                    continue
                if value not in self.allowed_answers:
                    raise SolutionValidationError(f"Ungueltige Antwortoption: {answer}")
                if value not in seen:
                    answers.append(value)
                    seen.add(value)
            if not answers:
                raise SolutionValidationError("answers darf pro Frage nicht leer sein.")
            normalized.append(QuestionAnswer(question=item.question, answers=answers))

        return AiSolution(
            explanation=solution.explanation,
            answers=normalized,
            confidence=solution.confidence,
            raw_response=solution.raw_response,
        )
