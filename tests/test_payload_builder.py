from datetime import datetime

from quiz_relay.config import HttpRelayConfig
from quiz_relay.models import AiSolution, AnswerOption, QuestionAnswer, RunContext
from quiz_relay.relay import build_relay_payload


def test_payload_uses_default_fields():
    context = RunContext.create("cli")
    solution = AiSolution("because", [QuestionAnswer(1, ["A"])], 0.9)
    payload = build_relay_payload(HttpRelayConfig(), context, solution)
    assert payload["task_id"] == context.task_id
    assert payload["answers"] == [{"question": 1, "answers": ["A"]}]
    assert payload["confidence"] == 0.9
    assert datetime.fromisoformat(payload["created_at"]).utcoffset() is not None
    assert not payload["created_at"].endswith("Z")
    assert "explanation" not in payload


def test_payload_fields_are_configurable():
    context = RunContext.create("cli")
    solution = AiSolution("because", [QuestionAnswer(1, ["A"])], None)
    payload = build_relay_payload(
        HttpRelayConfig(fields={"id": "context.task_id", "answer": "solution.answers_text", "reason": "solution.explanation"}),
        context,
        solution,
    )
    assert payload == {"id": context.task_id, "answer": "A", "reason": "because"}


def test_payload_maps_single_answer_to_vibe_n():
    context = RunContext.create("cli")
    solution = AiSolution("because", [QuestionAnswer(1, ["B"])], None)
    payload = build_relay_payload(
        HttpRelayConfig(fields={"n": "solution.vibe_n", "seq": "solution.vibe_seq"}),
        context,
        solution,
    )
    assert payload == {"n": "2"}


def test_payload_maps_multiple_answers_to_vibe_seq():
    context = RunContext.create("cli")
    solution = AiSolution("because", [QuestionAnswer(1, ["A", "3"])], None)
    payload = build_relay_payload(
        HttpRelayConfig(fields={"n": "solution.vibe_n", "seq": "solution.vibe_seq"}),
        context,
        solution,
    )
    assert payload == {"seq": "1,3"}


def test_payload_includes_question_text_and_options():
    context = RunContext.create("cli")
    solution = AiSolution(
        "because",
        [
            QuestionAnswer(
                question=1,
                answers=["2"],
                question_text="What is 2 + 2?",
                options=[AnswerOption("1", "3"), AnswerOption("2", "4")],
            )
        ],
        0.9,
    )
    payload = build_relay_payload(HttpRelayConfig(), context, solution)
    assert payload["answers"] == [
        {
            "question": 1,
            "answers": ["2"],
            "question_text": "What is 2 + 2?",
            "options": [{"id": "1", "text": "3"}, {"id": "2", "text": "4"}],
        }
    ]
