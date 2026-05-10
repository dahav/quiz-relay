from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ConfigurationError


@dataclass(frozen=True)
class AppConfig:
    name: str = "Quiz Relay"
    profile: str = "default"
    runtime_directory: Path = Path("runtime")
    save_ai_raw_response: bool = True
    allow_parallel_runs: bool = False


@dataclass(frozen=True)
class ScreenshotConfig:
    format: str = "png"
    delay_ms: int = 0
    monitor: int = 1


@dataclass(frozen=True)
class AiConfig:
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    timeout_seconds: float = 30
    response_language: str = "de"
    prompt_file: Path | None = Path(".prompt")
    openai_image_detail: str = "auto"
    max_tokens: int = 1024


@dataclass(frozen=True)
class HttpRelayConfig:
    enabled: bool = False
    url: str = "http://127.0.0.1:8080/solution"
    mode: str = "json"
    timeout_seconds: float = 2.0
    retries: int = 2
    fields: dict[str, str] | None = None


@dataclass(frozen=True)
class MouseConfig:
    event: str = "middle-click"


@dataclass(frozen=True)
class LoggingConfig:
    runs_file: Path = Path("runtime/logs/runs.jsonl")


@dataclass(frozen=True)
class Settings:
    app: AppConfig
    screenshot: ScreenshotConfig
    ai: AiConfig
    http_relay: HttpRelayConfig
    mouse: MouseConfig
    logging: LoggingConfig
    config_path: Path | None = None


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def _read_toml(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.is_file():
        raise ConfigurationError(f"Configuration file not found: {path}")
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigurationError(f"Configuration file is invalid: {exc}") from exc


def _path(value: str | Path | None) -> Path | None:
    if value is None or value == "":
        return None
    return Path(value).expanduser()


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ConfigurationError(f"Configuration section [{name}] must be a table.")
    return value


def load_settings(config_path: str | Path | None = None, profile: str | None = None) -> Settings:
    _load_dotenv()

    env_config = os.getenv("QUIZ_RELAY_CONFIG", "").strip()
    selected_path = Path(config_path).expanduser() if config_path else _path(env_config)
    data = _read_toml(selected_path)

    app_data = _section(data, "app")
    screenshot_data = _section(data, "screenshot")
    ai_data = _section(data, "ai")
    relay_data = _section(data, "http_relay")
    mouse_data = _section(data, "mouse") or _section(data, "mouse_trigger")
    logging_data = _section(data, "logging")

    selected_profile = profile or os.getenv("QUIZ_RELAY_PROFILE") or app_data.get("profile", "default")
    app = AppConfig(
        name=str(app_data.get("name", "Quiz Relay")),
        profile=str(selected_profile),
        runtime_directory=Path(app_data.get("runtime_directory", "runtime")),
        save_ai_raw_response=bool(app_data.get("save_ai_raw_response", True)),
        allow_parallel_runs=bool(app_data.get("allow_parallel_runs", False)),
    )
    screenshot = ScreenshotConfig(
        format=str(screenshot_data.get("format", "png")).lower(),
        delay_ms=int(screenshot_data.get("delay_ms", 0)),
        monitor=int(screenshot_data.get("monitor", 1)),
    )
    ai = AiConfig(
        provider=str(ai_data.get("provider", "openai")).lower(),
        model=str(ai_data.get("model", "gpt-4.1-mini")),
        timeout_seconds=float(ai_data.get("timeout_seconds", 30)),
        response_language=str(ai_data.get("response_language", "de")),
        prompt_file=_path(ai_data.get("prompt_file", ".prompt")),
        openai_image_detail=str(ai_data.get("openai_image_detail", "auto")),
        max_tokens=int(ai_data.get("max_tokens", 1024)),
    )
    relay_fields = relay_data.get("fields")
    if relay_fields is not None and not isinstance(relay_fields, dict):
        raise ConfigurationError("Configuration section [http_relay.fields] must be a table.")
    http_relay = HttpRelayConfig(
        enabled=bool(relay_data.get("enabled", False)),
        url=str(relay_data.get("url", "http://127.0.0.1:8080/solution")),
        mode=str(relay_data.get("mode", "json")).lower(),
        timeout_seconds=float(relay_data.get("timeout_seconds", 2.0)),
        retries=int(relay_data.get("retries", 2)),
        fields={str(key): str(value) for key, value in relay_fields.items()} if relay_fields else None,
    )
    mouse = MouseConfig(
        event=str(mouse_data.get("event", "middle-click")),
    )
    logging = LoggingConfig(
        runs_file=Path(logging_data.get("runs_file", "runtime/logs/runs.jsonl")),
    )

    if screenshot.format != "png":
        raise ConfigurationError("Only screenshot format 'png' is currently supported.")
    if http_relay.mode not in {"json", "query"}:
        raise ConfigurationError("http_relay.mode must be 'json' or 'query'.")
    if http_relay.retries < 0:
        raise ConfigurationError("http_relay.retries must not be negative.")
    return Settings(app, screenshot, ai, http_relay, mouse, logging, selected_path)
