from __future__ import annotations

import base64
import json
import sys
from datetime import datetime
from pathlib import Path

from quiz_relay.config import Settings
from quiz_relay.errors import AiResponseError, ConfigError, InvalidImageError, UnknownModeError
from quiz_relay.solution import Solution

BASE_MODE = "multiplechoice"

IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

DEFAULT_PROMPT = """Analyze the provided image.
Look for exactly one multiple-choice question.

Return only valid JSON in this schema:

{{
  "explanation": "Detailed reasoning for the answer.",
  "answers": [
    {{
      "question": 1,
      "question_text": "Full question text exactly as visible.",
      "options": [
        {{"id": "A", "text": "First visible answer option"}},
        {{"id": "B", "text": "Second visible answer option"}}
      ],
      "answers": ["A"]
    }}
  ],
  "confidence": 0.0
}}

Rules:
- Write the explanation in this language: {language}.
- Include the full visible question text in question_text.
- Include every visible answer option in options.
- Use the visible option identifier as id, such as A, B, C or 1, 2, 3.
- If an option has no visible identifier, assign A, B, C by reading order.
- Use uppercase letters for letter identifiers.
- Preserve answer option text as visible. Do not translate answer option text.
- Put only the correct option identifiers in answers.
- If multiple options are correct, include all correct identifiers in answers.
- If multiple questions are visible, include one object per question.
- If no multiple-choice question is visible, return an empty answers array with explanation "no question visible". Do not invent a question.
- Do not return Markdown code fences.
"""


def solve(settings: Settings, mode: str, image: Path | None = None) -> tuple[Solution, Path, str]:
    from quiz_relay.service import solve_image

    if image is not None:
        source, source_key = image, "image"
    else:
        source, source_key = capture_screenshot(settings), "screenshot"
    return solve_image(settings, mode, source), source, source_key


def available_modes(prompts_dir: Path) -> list[str]:
    if not prompts_dir.is_dir():
        return []
    return sorted(p.stem for p in prompts_dir.glob("*.md") if p.stem != BASE_MODE)


def load_mode(prompts_dir: Path, mode: str) -> str:
    if mode == BASE_MODE:
        raise UnknownModeError(f"'{BASE_MODE}' is the common base and cannot be used as a mode.")
    path = prompts_dir / f"{mode}.md"
    if not path.is_file():
        hint = ", ".join(available_modes(prompts_dir)) or "(none)"
        raise UnknownModeError(f"Unknown mode '{mode}'. Available: {hint}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise UnknownModeError(f"Mode file is empty: {path}")
    return text


def capture_screenshot(settings: Settings) -> Path:
    import mss
    import mss.tools

    out_dir = Path("runtime/screenshots")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.png"

    with mss.MSS() as sct:
        monitors = sct.monitors
        idx = settings.monitor
        if idx < 1 or idx >= len(monitors):
            raise InvalidImageError(f"Monitor {idx} is not available.")
        shot = sct.grab(monitors[idx])
        sample = bytes(shot.rgb)[:: max(1, len(shot.rgb) // 5000)]
        if max(sample) - min(sample) < 10:
            raise InvalidImageError(
                "Screenshot appears empty (near-uniform color). "
                "On Wayland, mss often returns a black image. Switch to an X11 session."
            )
        mss.tools.to_png(shot.rgb, shot.size, output=str(out))
    return out


def build_prompt(settings: Settings, mode: str) -> str:
    base = DEFAULT_PROMPT.format(language=settings.ai_response_language)
    extra = load_mode(settings.prompts_dir, mode)
    common_path = settings.prompts_dir / f"{BASE_MODE}.md"
    common = common_path.read_text(encoding="utf-8").strip() if common_path.is_file() else ""
    sections = [base, f"Mode: {mode}"]
    if common:
        sections.append(f"Common instructions:\n{common}")
    sections.append(f"Additional instructions:\n{extra}")
    return "\n".join(sections) + "\n"


def ask_ai(image_path: Path, settings: Settings, mode: str) -> str:
    from openai import OpenAI

    if not settings.openai_api_key:
        raise ConfigError("openai_api_key is not set in config.toml ([ai] section).")
    prompt = build_prompt(settings, mode)
    image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    mime = IMAGE_MIME_TYPES.get(image_path.suffix.lower(), "image/png")
    parts = [f"model={settings.ai_model}", f"mode={mode}"]
    if settings.ai_reasoning_effort:
        parts.append(f"effort={settings.ai_reasoning_effort}")
    parts.append(f"image={image_path}")
    print(f"calling AI... ({', '.join(parts)})", file=sys.stderr, flush=True)

    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.ai_timeout_seconds)
    kwargs: dict = {
        "model": settings.ai_model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": f"data:{mime};base64,{image_b64}"},
                ],
            }
        ],
    }
    if settings.ai_reasoning_effort:
        kwargs["reasoning"] = {"effort": settings.ai_reasoning_effort}
    return client.responses.create(**kwargs).output_text.strip()


def _strip_json_fence(text: str) -> str:
    return text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()


def parse_response(text: str) -> Solution:
    stripped = _strip_json_fence(text)
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        start, end = stripped.find("{"), stripped.rfind("}")
        if start == -1 or end < start:
            raise AiResponseError("AI response does not contain a JSON object.")
        data = json.loads(stripped[start : end + 1])
    if not isinstance(data, dict) or not isinstance(data.get("answers"), list):
        raise AiResponseError("AI response missing answers array.")
    if not data["answers"]:
        raise AiResponseError(f"AI found no question: {data.get('explanation') or 'no question visible'}")
    return Solution(raw=data)
