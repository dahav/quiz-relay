from quiz_relay.ai import parse_ai_response
from quiz_relay.errors import AiResponseParseError
from quiz_relay.models import AiRawResponse


def parse(text: str):
    return parse_ai_response(AiRawResponse(text=text, provider="test", model="test"))


def test_parses_valid_json():
    solution = parse('{"explanation":"ok","answers":[{"question":1,"answers":["A"]}],"confidence":0.5}')
    assert solution.explanation == "ok"
    assert solution.answers[0].question == 1
    assert solution.answers[0].answers == ["A"]
    assert solution.confidence == 0.5


def test_parses_question_text_and_answer_options():
    solution = parse(
        """
        {
          "explanation": "ok",
          "answers": [
            {
              "question": 1,
              "question_text": "What is 2 + 2?",
              "options": [
                {"id": "1", "text": "3"},
                {"id": "2", "text": "4"}
              ],
              "answers": ["2"]
            }
          ],
          "confidence": 0.5
        }
        """
    )
    answer = solution.answers[0]
    assert answer.question_text == "What is 2 + 2?"
    assert answer.options[0].id == "1"
    assert answer.options[0].text == "3"
    assert answer.options[1].id == "2"
    assert answer.options[1].text == "4"
    assert answer.answers == ["2"]


def test_parses_markdown_json_block():
    solution = parse('```json\n{"explanation":"ok","answers":[],"confidence":null}\n```')
    assert solution.answers == []
    assert solution.confidence is None


def test_rejects_missing_answers():
    try:
        parse('{"explanation":"ok"}')
    except AiResponseParseError as exc:
        assert "answers" in str(exc)
    else:
        raise AssertionError("expected AiResponseParseError")
