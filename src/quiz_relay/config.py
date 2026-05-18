from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ScreenshotConfig:
    monitor: int = 1


@dataclass(frozen=True)
class AiConfig:
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    reasoning_effort: str | None = None
    timeout_seconds: float = 30.0
    response_language: str = "de"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None


@dataclass(frozen=True)
class PromptsConfig:
    dir: Path = Path("prompts")


@dataclass(frozen=True)
class MouseConfig:
    event: str = "middle-click"


@dataclass(frozen=True)
class Settings:
    screenshot: ScreenshotConfig
    ai: AiConfig
    mouse: MouseConfig
    prompts: PromptsConfig
    relays: dict[str, dict[str, Any]] = field(default_factory=dict)


def load_settings(config_path: Path | None = None) -> Settings:
    path = config_path or Path("config.toml")
    if not path.is_file():
        raise SystemExit(f"Configuration file not found: {path}")
    data: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))

    return Settings(
        screenshot=_screenshot(data.get("screenshot", {})),
        ai=_ai(data.get("ai", {})),
        mouse=_mouse(data.get("mouse", {})),
        prompts=_prompts(data.get("prompts", {})),
        relays=_relays(data.get("relay", {})),
    )


def _screenshot(data: dict) -> ScreenshotConfig:
    return ScreenshotConfig(monitor=int(data.get("monitor", 1)))


def _ai(data: dict) -> AiConfig:
    effort = data.get("reasoning_effort")
    openai_key = data.get("openai_api_key")
    anthropic_key = data.get("anthropic_api_key")
    return AiConfig(
        provider=str(data.get("provider", "openai")).lower(),
        model=str(data.get("model", "gpt-4.1-mini")),
        reasoning_effort=str(effort).lower() if effort else None,
        timeout_seconds=float(data.get("timeout_seconds", 30.0)),
        response_language=str(data.get("response_language", "de")),
        openai_api_key=str(openai_key) if openai_key else None,
        anthropic_api_key=str(anthropic_key) if anthropic_key else None,
    )


def _prompts(data: dict) -> PromptsConfig:
    return PromptsConfig(dir=Path(data.get("dir", "prompts")).expanduser())


def _relays(data: dict) -> dict[str, dict[str, Any]]:
    return {name: dict(section) for name, section in data.items() if isinstance(section, dict)}


def _mouse(data: dict) -> MouseConfig:
    return MouseConfig(event=str(data.get("event", "middle-click")))
