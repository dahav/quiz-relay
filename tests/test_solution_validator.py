from quiz_relay.ai import validate_solution
from quiz_relay.errors import SolutionValidationError
from quiz_relay.models import AiSolution, AnswerOption, QuestionAnswer


def test_normalizes_answer_letters_and_removes_duplicates():
    solution = AiSolution("ok", [QuestionAnswer(1, ["a", "A", " b "])], 0.7)
    validated = validate_solution(solution)
    assert validated.answers[0].answers == ["A", "B"]


def test_validates_numeric_answers_against_options():
    solution = AiSolution(
        "ok",
        [
            QuestionAnswer(
                question=1,
                question_text=" Pick one ",
                options=[AnswerOption("1", "First"), AnswerOption("2", "Second")],
                answers=["2"],
            )
        ],
        0.7,
    )
    validated = validate_solution(solution)
    assert validated.answers[0].question_text == "Pick one"
    assert validated.answers[0].options[0].id == "1"
    assert validated.answers[0].options[1].id == "2"
    assert validated.answers[0].answers == ["2"]


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


def test_rejects_answer_that_is_not_in_options():
    try:
        validate_solution(
            AiSolution(
                "ok",
                [QuestionAnswer(1, ["3"], options=[AnswerOption("1", "First")])],
                None,
            )
        )
    except SolutionValidationError as exc:
        assert "Invalid answer option" in str(exc)
    else:
        raise AssertionError("expected SolutionValidationError")
