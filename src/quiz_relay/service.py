from __future__ import annotations

from pathlib import Path
from typing import Any

from quiz_relay.config import Settings
from quiz_relay.core import IMAGE_MIME_TYPES, ask_ai, load_mode, parse_response
from quiz_relay.errors import InvalidImageError
from quiz_relay.relays import build_relay
from quiz_relay.solution import Solution, answers_to_pulses


def solve_image(settings: Settings, mode: str, image_path: Path) -> Solution:
    load_mode(settings.prompts_dir, mode)
    validate_image_path(image_path)
    return parse_response(ask_ai(image_path, settings, mode))


def validate_image_path(image_path: Path) -> None:
    if not image_path.is_file():
        raise InvalidImageError(f"Image file not found: {image_path}")
    if image_path.suffix.lower() not in IMAGE_MIME_TYPES:
        supported = ", ".join(sorted(IMAGE_MIME_TYPES))
        raise InvalidImageError(f"Unsupported image format '{image_path.suffix}'. Supported: {supported}")


def solution_payload(mode: str, image_path: Path, solution: Solution) -> dict[str, Any]:
    answer_ids = solution.all_answer_ids
    return {
        "mode": mode,
        "image": str(image_path),
        "solution": solution.to_dict(),
        "answer_ids": answer_ids,
        "pulses": answers_to_pulses(answer_ids),
    }


def dispatch_relays(settings: Settings, names: list[str], pulses: list[int]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for name in names:
        try:
            relay = build_relay(name, settings.relays.get(name, {}))
            result = relay.send(pulses)
        except (SystemExit, Exception) as exc:
            result = {"sent": False, "error": str(exc)}
        results[name] = result
    return results
