from __future__ import annotations

import tomllib
from dataclasses import dataclass
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
class RelayConfig:
    enabled: bool = False
    url: str = "http://127.0.0.1:8080/solution"
    timeout_seconds: float = 2.0
    on: int = 120
    off: int = 80
    pause: int = 500
    duty: int = 170


@dataclass(frozen=True)
class MouseConfig:
    event: str = "middle-click"


@dataclass(frozen=True)
class Settings:
    screenshot: ScreenshotConfig
    ai: AiConfig
    relay: RelayConfig
    mouse: MouseConfig
    prompts: PromptsConfig


def load_settings(config_path: Path | None = None) -> Settings:
    path = config_path or Path("config.toml")
    if not path.is_file():
        raise SystemExit(f"Configuration file not found: {path}")
    data: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))

    return Settings(
        screenshot=_screenshot(data.get("screenshot", {})),
        ai=_ai(data.get("ai", {})),
        relay=_relay(data.get("relay", {})),
        mouse=_mouse(data.get("mouse", {})),
        prompts=_prompts(data.get("prompts", {})),
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


def _relay(data: dict) -> RelayConfig:
    return RelayConfig(
        enabled=bool(data.get("enabled", False)),
        url=str(data.get("url", "http://127.0.0.1:8080/solution")),
        timeout_seconds=float(data.get("timeout_seconds", 2.0)),
        on=int(data.get("on", 120)),
        off=int(data.get("off", 80)),
        pause=int(data.get("pause", 500)),
        duty=int(data.get("duty", 170)),
    )


def _mouse(data: dict) -> MouseConfig:
    return MouseConfig(event=str(data.get("event", "middle-click")))
