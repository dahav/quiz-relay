from quiz_relay.ai import validate_solution
from quiz_relay.errors import SolutionValidationError
from quiz_relay.models import AiSolution, QuestionAnswer


def test_normalizes_answer_letters_and_removes_duplicates():
    solution = AiSolution("ok", [QuestionAnswer(1, ["a", "A", " b "])], 0.7)
    validated = validate_solution(solution)
    assert validated.answers[0].answers == ["A", "B"]


def test_rejects_invalid_confidence():
    try:
        validate_solution(AiSolution("ok", [], 1.5))
    except SolutionValidationError as exc:
        assert "confidence" in str(exc)
    else:
        raise AssertionError("expected SolutionValidationError")


def test_rejects_empty_answer_for_visible_question():
    try:
        validate_solution(AiSolution("ok", [QuestionAnswer(1, [])], None))
    except SolutionValidationError as exc:
        assert "answers" in str(exc)
    else:
        raise AssertionError("expected SolutionValidationError")
