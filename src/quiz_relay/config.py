from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ConfigurationError

TomlTable = dict[str, Any]


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


def _read_toml(path: Path | None) -> TomlTable:
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


def _section(data: TomlTable, name: str) -> TomlTable:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ConfigurationError(f"Configuration section [{name}] must be a table.")
    return value


def _selected_config_path(config_path: str | Path | None) -> Path | None:
    env_config = os.getenv("QUIZ_RELAY_CONFIG", "").strip()
    return Path(config_path).expanduser() if config_path else _path(env_config)


def _selected_profile(profile: str | None, app_data: TomlTable) -> str:
    return str(profile or os.getenv("QUIZ_RELAY_PROFILE") or app_data.get("profile", "default"))


def _app_config(data: TomlTable, selected_profile: str) -> AppConfig:
    return AppConfig(
        name=str(data.get("name", "Quiz Relay")),
        profile=str(selected_profile),
        runtime_directory=Path(data.get("runtime_directory", "runtime")),
        save_ai_raw_response=bool(data.get("save_ai_raw_response", True)),
        allow_parallel_runs=bool(data.get("allow_parallel_runs", False)),
    )


def _screenshot_config(data: TomlTable) -> ScreenshotConfig:
    return ScreenshotConfig(
        format=str(data.get("format", "png")).lower(),
        delay_ms=int(data.get("delay_ms", 0)),
        monitor=int(data.get("monitor", 1)),
    )


def _ai_config(data: TomlTable) -> AiConfig:
    return AiConfig(
        provider=str(data.get("provider", "openai")).lower(),
        model=str(data.get("model", "gpt-4.1-mini")),
        timeout_seconds=float(data.get("timeout_seconds", 30)),
        response_language=str(data.get("response_language", "de")),
        prompt_file=_path(data.get("prompt_file", ".prompt")),
        openai_image_detail=str(data.get("openai_image_detail", "auto")),
        max_tokens=int(data.get("max_tokens", 1024)),
    )


def _http_relay_config(data: TomlTable) -> HttpRelayConfig:
    relay_fields = data.get("fields")
    if relay_fields is not None and not isinstance(relay_fields, dict):
        raise ConfigurationError("Configuration section [http_relay.fields] must be a table.")
    return HttpRelayConfig(
        enabled=bool(data.get("enabled", False)),
        url=str(data.get("url", "http://127.0.0.1:8080/solution")),
        mode=str(data.get("mode", "json")).lower(),
        timeout_seconds=float(data.get("timeout_seconds", 2.0)),
        retries=int(data.get("retries", 2)),
        fields={str(key): str(value) for key, value in relay_fields.items()} if relay_fields else None,
    )


def _mouse_section(data: TomlTable) -> TomlTable:
    mouse_data = _section(data, "mouse")
    return mouse_data or _section(data, "mouse_trigger")


def _mouse_config(data: TomlTable) -> MouseConfig:
    return MouseConfig(event=str(data.get("event", "middle-click")))


def _logging_config(data: TomlTable) -> LoggingConfig:
    return LoggingConfig(runs_file=Path(data.get("runs_file", "runtime/logs/runs.jsonl")))


def _validate_settings(settings: Settings) -> None:
    if settings.screenshot.format != "png":
        raise ConfigurationError("Only screenshot format 'png' is currently supported.")
    if settings.http_relay.mode not in {"json", "query"}:
        raise ConfigurationError("http_relay.mode must be 'json' or 'query'.")
    if settings.http_relay.retries < 0:
        raise ConfigurationError("http_relay.retries must not be negative.")


def load_settings(config_path: str | Path | None = None, profile: str | None = None) -> Settings:
    """Load settings from defaults, environment, and an optional TOML config file."""
    _load_dotenv()

    selected_path = _selected_config_path(config_path)
    data = _read_toml(selected_path)

    app_data = _section(data, "app")
    selected_profile = _selected_profile(profile, app_data)
    settings = Settings(
        app=_app_config(app_data, selected_profile),
        screenshot=_screenshot_config(_section(data, "screenshot")),
        ai=_ai_config(_section(data, "ai")),
        http_relay=_http_relay_config(_section(data, "http_relay")),
        mouse=_mouse_config(_mouse_section(data)),
        logging=_logging_config(_section(data, "logging")),
        config_path=selected_path,
    )
    _validate_settings(settings)
    return settings
