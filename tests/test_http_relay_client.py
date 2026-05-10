import json
import urllib.parse

from quiz_relay.config import HttpRelayConfig
from quiz_relay.relay import build_relay_request


def test_json_mode_builds_post_request():
    request = build_relay_request(
        HttpRelayConfig(url="http://example.test/hook", mode="json"),
        {"answer": "A", "confidence": 0.8},
    )
    assert request.get_method() == "POST"
    assert request.full_url == "http://example.test/hook"
    assert request.headers["Content-type"] == "application/json"
    assert json.loads(request.data.decode("utf-8")) == {"answer": "A", "confidence": 0.8}


def test_query_mode_builds_get_request_with_encoded_parameters():
    request = build_relay_request(
        HttpRelayConfig(url="http://example.test/hook?token=abc", mode="query"),
        {"answer": "A", "answers": [{"question": 1, "answers": ["A"]}]},
    )
    parsed = urllib.parse.urlparse(request.full_url)
    query = urllib.parse.parse_qs(parsed.query)
    assert request.get_method() == "GET"
    assert query["token"] == ["abc"]
    assert query["answer"] == ["A"]
    assert query["answers"] == ['[{"question":1,"answers":["A"]}]']
