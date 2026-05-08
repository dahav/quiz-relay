from __future__ import annotations

from datetime import UTC, datetime

from quiz_relay.ai.models import AiSolution
from quiz_relay.config import Esp32Config
from quiz_relay.pipeline.run_context import RunContext


class Esp32PayloadBuilder:
    def __init__(self, config: Esp32Config) -> None:
        self.config = config

    def build(self, context: RunContext, solution: AiSolution) -> dict:
        payload = {
            "task_id": context.task_id,
            "source": context.source,
            "answers": [
                {
                    "question": item.question,
                    "answers": item.answers,
                }
                for item in solution.answers
            ],
        }
        if solution.confidence is not None:
            payload["confidence"] = solution.confidence
        if self.config.send_explanation:
            payload["explanation"] = solution.explanation
        payload["created_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        return payload
