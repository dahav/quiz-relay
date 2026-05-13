from __future__ import annotations

import base64
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from quiz_relay.config import Settings

FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", flags=re.DOTALL | re.IGNORECASE)

BASE_MODE = "multiplechoice"

IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

VIBE_PULSE = {letter: i for i, letter in enumerate("ABCDEFGHI", 1)} | {str(i): i for i in range(1, 10)}

DEFAULT_PROMPT = """Analyze the provided image.
Look for one or more multiple-choice questions.

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


def solve(settings: Settings, mode: str, image: Path | None = None) -> dict:
    _load_mode(settings.prompts.dir, mode)
    if image is not None:
        source = _validate_image(image)
        source_key = "image"
    else:
        source = capture_screenshot(settings)
        source_key = "screenshot"
    raw = ask_ai(source, settings, mode)
    solution = parse_response(raw)
    result: dict = {"mode": mode, source_key: str(source), "solution": solution}
    if settings.relay.enabled:
        result["relay"] = send_relay(settings, solution)
    return result


def _validate_image(path: Path) -> Path:
    if not path.is_file():
        raise SystemExit(f"Image file not found: {path}")
    if path.suffix.lower() not in IMAGE_MIME_TYPES:
        supported = ", ".join(sorted(IMAGE_MIME_TYPES))
        raise SystemExit(f"Unsupported image format '{path.suffix}'. Supported: {supported}")
    return path


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def available_modes(prompts_dir: Path) -> list[str]:
    if not prompts_dir.is_dir():
        return []
    return sorted(path.stem for path in prompts_dir.glob("*.md") if path.stem != BASE_MODE)


def validate_mode(prompts_dir: Path, mode: str) -> None:
    _load_mode(prompts_dir, mode)


def _load_mode(prompts_dir: Path, mode: str) -> str:
    if mode == BASE_MODE:
        raise SystemExit(f"'{BASE_MODE}' is the common base and cannot be used as a mode.")
    path = prompts_dir / f"{mode}.md"
    if not path.is_file():
        available = available_modes(prompts_dir)
        hint = ", ".join(available) if available else "(none)"
        raise SystemExit(f"Unknown mode '{mode}'. Available: {hint}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise SystemExit(f"Mode file is empty: {path}")
    return text


def capture_screenshot(settings: Settings) -> Path:
    import mss
    import mss.tools

    out_dir = Path("runtime/screenshots")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.png"

    with mss.MSS() as sct:
        monitors = sct.monitors
        idx = settings.screenshot.monitor
        if idx < 1 or idx >= len(monitors):
            raise SystemExit(f"Monitor {idx} is not available.")
        shot = sct.grab(monitors[idx])
        _ensure_screenshot_has_content(shot.rgb)
        mss.tools.to_png(shot.rgb, shot.size, output=str(out))
    return out


def _ensure_screenshot_has_content(rgb: bytes) -> None:
    sample = bytes(rgb)[:: max(1, len(rgb) // 5000)]
    if max(sample) - min(sample) < 10:
        raise SystemExit(
            "Screenshot appears empty (near-uniform color). "
            "On Wayland, mss often returns a black image. Switch to an X11 session."
        )


def build_prompt(settings: Settings, mode: str) -> str:
    base = DEFAULT_PROMPT.format(language=settings.ai.response_language)
    extra = _load_mode(settings.prompts.dir, mode)
    common_path = settings.prompts.dir / f"{BASE_MODE}.md"
    common = common_path.read_text(encoding="utf-8").strip() if common_path.is_file() else ""
    sections = [base, f"Mode: {mode}"]
    if common:
        sections.append(f"Common instructions:\n{common}")
    sections.append(f"Additional instructions:\n{extra}")
    return "\n".join(sections) + "\n"


def ask_ai(image_path: Path, settings: Settings, mode: str) -> str:
    prompt = build_prompt(settings, mode)
    image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    mime = IMAGE_MIME_TYPES.get(image_path.suffix.lower(), "image/png")
    provider = settings.ai.provider
    parts = [f"provider={provider}", f"model={settings.ai.model}", f"mode={mode}"]
    if settings.ai.reasoning_effort:
        parts.append(f"effort={settings.ai.reasoning_effort}")
    parts.append(f"image={_display_path(image_path)}")
    print(f"calling AI... ({', '.join(parts)})", file=sys.stderr, flush=True)
    if provider in {"openai", "chatgpt"}:
        return _ask_openai(prompt, image_b64, mime, settings)
    if provider in {"anthropic", "claude"}:
        return _ask_anthropic(prompt, image_b64, mime, settings)
    raise SystemExit(f"Unknown AI provider: {provider}")


def _ask_openai(prompt: str, image_b64: str, mime: str, settings: Settings) -> str:
    from openai import OpenAI

    if not settings.ai.openai_api_key:
        raise SystemExit("openai_api_key is not set in config.toml ([ai] section).")
    client = OpenAI(api_key=settings.ai.openai_api_key, timeout=settings.ai.timeout_seconds)
    kwargs: dict = {
        "model": settings.ai.model,
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
    if settings.ai.reasoning_effort:
        kwargs["reasoning"] = {"effort": settings.ai.reasoning_effort}
    response = client.responses.create(**kwargs)
    return response.output_text.strip()


def _ask_anthropic(prompt: str, image_b64: str, mime: str, settings: Settings) -> str:
    import anthropic

    if not settings.ai.anthropic_api_key:
        raise SystemExit("anthropic_api_key is not set in config.toml ([ai] section).")
    client = anthropic.Anthropic(api_key=settings.ai.anthropic_api_key, timeout=settings.ai.timeout_seconds)
    message = client.messages.create(
        model=settings.ai.model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": mime, "data": image_b64},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    return "\n".join(b.text for b in message.content if getattr(b, "type", None) == "text").strip()


def parse_response(text: str) -> dict:
    payload = _extract_json(text)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"AI response does not contain valid JSON: {exc}")
    if not isinstance(data, dict) or not isinstance(data.get("answers"), list):
        raise SystemExit("AI response missing answers array.")
    if not data["answers"]:
        explanation = data.get("explanation") or "no question visible"
        raise SystemExit(f"AI found no question: {explanation}")
    for item in data["answers"]:
        if isinstance(item, dict) and isinstance(item.get("answers"), list):
            item["answers"] = [a.strip().upper() for a in item["answers"] if isinstance(a, str)]
    return data


def _extract_json(text: str) -> str:
    stripped = text.strip()
    fence = FENCED_JSON_RE.search(stripped)
    if fence:
        return fence.group(1).strip()
    start, end = stripped.find("{"), stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise SystemExit("AI response does not contain a JSON object.")
    return stripped[start : end + 1]


def send_relay(settings: Settings, solution: dict) -> dict:
    letters = [a for item in solution.get("answers", []) if isinstance(item, dict) for a in item.get("answers", [])]
    pulses = [str(VIBE_PULSE[a]) for a in letters if a in VIBE_PULSE]
    params: dict[str, str] = {
        "on": str(settings.relay.on),
        "off": str(settings.relay.off),
        "pause": str(settings.relay.pause),
        "duty": str(settings.relay.duty),
    }
    if len(pulses) == 1:
        params["n"] = pulses[0]
    elif len(pulses) > 1:
        params["seq"] = ",".join(pulses[:8])

    url = settings.relay.url
    sep = "&" if urllib.parse.urlparse(url).query else "?"
    full_url = f"{url}{sep}{urllib.parse.urlencode(params)}"
    print(f"relay GET {full_url}", file=sys.stderr, flush=True)
    try:
        with urllib.request.urlopen(full_url, timeout=settings.relay.timeout_seconds) as response:
            print(f"relay <- {response.status}", file=sys.stderr, flush=True)
            return {"sent": 200 <= response.status < 300, "status": response.status}
    except Exception as exc:
        print(f"relay error: {exc}", file=sys.stderr, flush=True)
        return {"sent": False, "error": str(exc)}
