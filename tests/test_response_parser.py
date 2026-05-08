from quiz_relay.ai.models import AiRawResponse
from quiz_relay.ai.response_parser import AiResponseParser
from quiz_relay.errors import AiResponseParseError


def parse(text: str):
    return AiResponseParser().parse(AiRawResponse(text=text, provider="test", model="test"))


def test_parses_valid_json():
    solution = parse('{"explanation":"ok","answers":[{"question":1,"answers":["A"]}],"confidence":0.5}')
    assert solution.explanation == "ok"
    assert solution.answers[0].question == 1
    assert solution.answers[0].answers == ["A"]
    assert solution.confidence == 0.5


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
