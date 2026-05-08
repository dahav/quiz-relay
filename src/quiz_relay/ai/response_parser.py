from __future__ import annotations

import json
import re
from typing import Any

from quiz_relay.ai.models import AiRawResponse, AiSolution, QuestionAnswer
from quiz_relay.errors import AiResponseParseError


class AiResponseParser:
    def parse(self, raw: AiRawResponse) -> AiSolution:
        payload = self._extract_json(raw.text)
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise AiResponseParseError(f"KI-Antwort enthaelt kein valides JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise AiResponseParseError("KI-Antwort muss ein JSON-Objekt sein.")
        answers = data.get("answers")
        if not isinstance(answers, list):
            raise AiResponseParseError("Feld 'answers' fehlt oder ist kein Array.")
        parsed_answers = [self._parse_answer(item) for item in answers]
        confidence = data.get("confidence")
        if confidence is not None and not isinstance(confidence, (int, float)):
            raise AiResponseParseError("Feld 'confidence' muss numerisch oder null sein.")
        explanation = data.get("explanation", "")
        if not isinstance(explanation, str):
            raise AiResponseParseError("Feld 'explanation' muss ein String sein.")
        return AiSolution(
            explanation=explanation,
            answers=parsed_answers,
            confidence=float(confidence) if confidence is not None else None,
            raw_response=raw.text,
        )

    def _parse_answer(self, item: Any) -> QuestionAnswer:
        if not isinstance(item, dict):
            raise AiResponseParseError("Ein answers-Eintrag muss ein Objekt sein.")
        question = item.get("question")
        answers = item.get("answers")
        if not isinstance(question, int):
            raise AiResponseParseError("question muss eine Zahl sein.")
        if not isinstance(answers, list) or not all(isinstance(value, str) for value in answers):
            raise AiResponseParseError("answers muss ein String-Array sein.")
        return QuestionAnswer(question=question, answers=list(answers))

    def _extract_json(self, text: str) -> str:
        stripped = text.strip()
        fence = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
        if fence:
            return fence.group(1).strip()
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise AiResponseParseError("KI-Antwort enthaelt kein JSON-Objekt.")
        return stripped[start : end + 1]
