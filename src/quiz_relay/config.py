from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Settings:
    monitor: int = 1
    ai_model: str = "gpt-4.1-mini"
    ai_reasoning_effort: str | None = None
    ai_timeout_seconds: float = 30.0
    ai_response_language: str = "de"
    openai_api_key: str | None = None
    mouse_event: str = "middle-click"
    prompts_dir: Path = Path("prompts")
    relays: dict[str, dict[str, Any]] = field(default_factory=dict)


def load_settings(config_path: Path | None = None) -> Settings:
    path = config_path or Path("config.toml")
    if not path.is_file():
        raise SystemExit(f"Configuration file not found: {path}")
    data: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))

    screenshot = data.get("screenshot", {})
    ai = data.get("ai", {})
    mouse = data.get("mouse", {})
    prompts = data.get("prompts", {})
    effort = ai.get("reasoning_effort")
    openai_key = ai.get("openai_api_key")
    relays = {name: dict(s) for name, s in data.get("relay", {}).items() if isinstance(s, dict)}

    return Settings(
        monitor=int(screenshot.get("monitor", 1)),
        ai_model=str(ai.get("model", "gpt-4.1-mini")),
        ai_reasoning_effort=str(effort).lower() if effort else None,
        ai_timeout_seconds=float(ai.get("timeout_seconds", 30.0)),
        ai_response_language=str(ai.get("response_language", "de")),
        openai_api_key=str(openai_key) if openai_key else None,
        mouse_event=str(mouse.get("event", "middle-click")),
        prompts_dir=Path(prompts.get("dir", "prompts")).expanduser(),
        relays=relays,
    )
