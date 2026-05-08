from quiz_relay.ai.models import AiSolution, QuestionAnswer
from quiz_relay.ai.solution_validator import SolutionValidator
from quiz_relay.errors import SolutionValidationError


def test_normalizes_answer_letters_and_removes_duplicates():
    solution = AiSolution("ok", [QuestionAnswer(1, ["a", "A", " b "])], 0.7)
    validated = SolutionValidator().validate(solution)
    assert validated.answers[0].answers == ["A", "B"]


def test_rejects_invalid_confidence():
    try:
        SolutionValidator().validate(AiSolution("ok", [], 1.5))
    except SolutionValidationError as exc:
        assert "confidence" in str(exc)
    else:
        raise AssertionError("expected SolutionValidationError")


def test_rejects_empty_answer_for_visible_question():
    try:
        SolutionValidator().validate(AiSolution("ok", [QuestionAnswer(1, [])], None))
    except SolutionValidationError as exc:
        assert "answers" in str(exc)
    else:
        raise AssertionError("expected SolutionValidationError")
