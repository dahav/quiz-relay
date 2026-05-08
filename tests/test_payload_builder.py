from quiz_relay.ai.models import AiSolution, QuestionAnswer
from quiz_relay.config import Esp32Config
from quiz_relay.esp32.payload_builder import Esp32PayloadBuilder
from quiz_relay.pipeline.run_context import RunContext


def test_payload_omits_explanation_by_default():
    context = RunContext.create("cli")
    solution = AiSolution("because", [QuestionAnswer(1, ["A"])], 0.9)
    payload = Esp32PayloadBuilder(Esp32Config(send_explanation=False)).build(context, solution)
    assert payload["task_id"] == context.task_id
    assert payload["answers"] == [{"question": 1, "answers": ["A"]}]
    assert payload["confidence"] == 0.9
    assert "explanation" not in payload


def test_payload_can_include_explanation():
    context = RunContext.create("cli")
    solution = AiSolution("because", [QuestionAnswer(1, ["A"])], None)
    payload = Esp32PayloadBuilder(Esp32Config(send_explanation=True)).build(context, solution)
    assert payload["explanation"] == "because"
