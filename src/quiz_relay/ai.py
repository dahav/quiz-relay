from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

from quiz_relay.config import AiConfig
from quiz_relay.errors import AiRequestError, AiResponseParseError, SolutionValidationError
from quiz_relay.models import AiRawResponse, AiSolution, QuestionAnswer, ScreenshotResult

FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", flags=re.DOTALL | re.IGNORECASE)


def analyze_image(image: ScreenshotResult, config: AiConfig, base_dir: Path = Path(".")) -> AiRawResponse:
    """Send a screenshot to the configured AI provider and return the raw text response."""
    prompt = build_prompt(config, base_dir=base_dir)
    provider = config.provider.lower()
    if provider in {"openai", "chatgpt"}:
        text = analyze_with_openai(image, prompt, config)
        return AiRawResponse(text=text, provider="openai", model=config.model)
    if provider in {"anthropic", "claude"}:
        text = analyze_with_anthropic(image, prompt, config)
        return AiRawResponse(text=text, provider="anthropic", model=config.model)
    raise AiRequestError(f"Unknown AI provider: {config.provider}")


def build_prompt(config: AiConfig, base_dir: Path = Path(".")) -> str:
    """Build the prompt from the default instructions and an optional prompt file."""
    prompt = _base_prompt(config.response_language)
    extra = read_prompt_file(config, base_dir=base_dir)
    if extra:
        prompt = f"{prompt}\nAdditional instructions:\n{extra}\n"
    return prompt


def _base_prompt(response_language: str) -> str:
    return f"""Analyze the provided image.
Look for one or more multiple-choice questions.

Return only valid JSON in this schema:

{{
  "explanation": "Detailed reasoning for the answer.",
  "answers": [
    {{"question": 1, "answers": ["A"]}}
  ],
  "confidence": 0.0
}}

Rules:
- Write the explanation in this language: {response_language}.
- Use uppercase option letters such as A, B, C, D.
- If multiple options are correct, include all letters in the array.
- If multiple questions are visible, include one object per question.
- If no multiple-choice question is visible, return an empty answers array and explain why.
- Do not return Markdown code fences.
"""


def read_prompt_file(config: AiConfig, base_dir: Path = Path(".")) -> str:
    """Return additional prompt instructions, or an empty string when no file is configured."""
    if config.prompt_file is None:
        return ""
    prompt_path = config.prompt_file
    if not prompt_path.is_absolute():
        prompt_path = base_dir / prompt_path
    if not prompt_path.is_file():
        return ""
    return prompt_path.read_text(encoding="utf-8").strip()


def analyze_with_openai(image: ScreenshotResult, prompt: str, config: AiConfig) -> str:
    """Run the OpenAI image analysis request and return plain response text."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AiRequestError("The Python package 'openai' is not installed.") from exc

    image_data = _base64_image(image)
    try:
        client = OpenAI(timeout=config.timeout_seconds)
        response = client.responses.create(
            model=config.model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_image",
                            "image_url": f"data:{image.mime_type};base64,{image_data}",
                            "detail": config.openai_image_detail,
                        },
                    ],
                }
            ],
        )
        return response.output_text.strip()
    except Exception as exc:
        raise AiRequestError(f"OpenAI request failed: {exc}") from exc


def analyze_with_anthropic(image: ScreenshotResult, prompt: str, config: AiConfig) -> str:
    """Run the Anthropic image analysis request and return plain response text."""
    try:
        import anthropic
    except ImportError as exc:
        raise AiRequestError("The Python package 'anthropic' is not installed.") from exc

    image_data = _base64_image(image)
    try:
        client = anthropic.Anthropic(timeout=config.timeout_seconds)
        message = client.messages.create(
            model=config.model,
            max_tokens=config.max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image.mime_type,
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        return _anthropic_text(message)
    except Exception as exc:
        raise AiRequestError(f"Anthropic request failed: {exc}") from exc


def parse_ai_response(raw: AiRawResponse) -> AiSolution:
    """Parse the provider response into the internal solution model."""
    payload = _extract_json(raw.text)
    data = _load_response_object(payload)
    return _solution_from_response(data, raw.text)


def _load_response_object(payload: str) -> dict[str, Any]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise AiResponseParseError(f"AI response does not contain valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise AiResponseParseError("AI response must be a JSON object.")
    return data


def _solution_from_response(data: dict[str, Any], raw_text: str) -> AiSolution:
    answers = data.get("answers")
    if not isinstance(answers, list):
        raise AiResponseParseError("Field 'answers' is missing or is not an array.")
    parsed_answers = [_parse_answer(item) for item in answers]
    confidence = data.get("confidence")
    if confidence is not None and not isinstance(confidence, (int, float)):
        raise AiResponseParseError("Field 'confidence' must be numeric or null.")
    explanation = data.get("explanation", "")
    if not isinstance(explanation, str):
        raise AiResponseParseError("Field 'explanation' must be a string.")
    return AiSolution(
        explanation=explanation,
        answers=parsed_answers,
        confidence=float(confidence) if confidence is not None else None,
        raw_response=raw_text,
    )


def validate_solution(solution: AiSolution, allowed_answers: set[str] | None = None) -> AiSolution:
    """Normalize answer letters and reject structurally invalid solutions."""
    allowed = allowed_answers or set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    _validate_confidence(solution.confidence)
    normalized = [_normalize_question_answer(item, allowed) for item in solution.answers]
    return AiSolution(
        explanation=solution.explanation,
        answers=normalized,
        confidence=solution.confidence,
        raw_response=solution.raw_response,
    )


def _base64_image(image: ScreenshotResult) -> str:
    return base64.b64encode(Path(image.path).read_bytes()).decode("ascii")


def _anthropic_text(message: Any) -> str:
    text_blocks = [
        block.text
        for block in message.content
        if getattr(block, "type", None) == "text"
    ]
    return "\n".join(text_blocks).strip()


def _parse_answer(item: Any) -> QuestionAnswer:
    if not isinstance(item, dict):
        raise AiResponseParseError("An answers entry must be an object.")
    question = item.get("question")
    answers = item.get("answers")
    if not isinstance(question, int):
        raise AiResponseParseError("question must be a number.")
    if not isinstance(answers, list) or not all(isinstance(value, str) for value in answers):
        raise AiResponseParseError("answers must be a string array.")
    return QuestionAnswer(question=question, answers=list(answers))


def _extract_json(text: str) -> str:
    stripped = text.strip()
    fence = FENCED_JSON_RE.search(stripped)
    if fence:
        return fence.group(1).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise AiResponseParseError("AI response does not contain a JSON object.")
    return stripped[start : end + 1]


def _validate_confidence(confidence: float | None) -> None:
    if confidence is not None and not 0 <= confidence <= 1:
        raise SolutionValidationError("confidence must be between 0 and 1.")


def _normalize_question_answer(item: QuestionAnswer, allowed_answers: set[str]) -> QuestionAnswer:
    if item.question < 1:
        raise SolutionValidationError("question must be greater than or equal to 1.")
    answers = _normalize_answer_letters(item.answers, allowed_answers)
    if not answers:
        raise SolutionValidationError("answers must not be empty for a visible question.")
    return QuestionAnswer(question=item.question, answers=answers)


def _normalize_answer_letters(answers: list[str], allowed_answers: set[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for answer in answers:
        value = answer.strip().upper()
        if not value:
            continue
        if value not in allowed_answers:
            raise SolutionValidationError(f"Invalid answer option: {answer}")
        if value not in seen:
            normalized.append(value)
            seen.add(value)
    return normalized
