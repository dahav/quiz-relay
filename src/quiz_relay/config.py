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
    save_screenshots: bool = True
    save_ai_raw_response: bool = True
    allow_parallel_runs: bool = False
    minimum_seconds_between_runs: float = 1.5


@dataclass(frozen=True)
class ScreenshotConfig:
    backend: str = "mss"
    format: str = "png"
    delay_ms: int = 0
    monitor: int = 1
    region: str = "full"
    preprocess: bool = False


@dataclass(frozen=True)
class AiConfig:
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    timeout_seconds: float = 30
    response_language: str = "de"
    strict_json: bool = True
    prompt_file: Path | None = Path(".prompt")
    openai_image_detail: str = "auto"
    max_tokens: int = 1024


@dataclass(frozen=True)
class Esp32Config:
    enabled: bool = False
    base_url: str = "http://192.168.178.55"
    endpoint: str = "/solution"
    timeout_seconds: float = 2.0
    retries: int = 2
    send_explanation: bool = False


@dataclass(frozen=True)
class MouseTriggerConfig:
    enabled: bool = True
    event: str = "middle-click"
    debounce_ms: int = 750
    ignore_while_running: bool = True


@dataclass(frozen=True)
class LoggingConfig:
    level: str = "INFO"
    runs_file: Path = Path("runtime/logs/runs.jsonl")
    app_log_file: Path = Path("runtime/logs/app.log")
    error_log_file: Path = Path("runtime/logs/errors.log")


@dataclass(frozen=True)
class Settings:
    app: AppConfig
    screenshot: ScreenshotConfig
    ai: AiConfig
    esp32: Esp32Config
    mouse_trigger: MouseTriggerConfig
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
        raise ConfigurationError(f"Konfigurationsdatei nicht gefunden: {path}")
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigurationError(f"Konfigurationsdatei ist ungueltig: {exc}") from exc


def _path(value: str | Path | None) -> Path | None:
    if value is None or value == "":
        return None
    return Path(value).expanduser()


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ConfigurationError(f"Konfigurationssektion [{name}] muss eine Tabelle sein.")
    return value


def load_settings(config_path: str | Path | None = None, profile: str | None = None) -> Settings:
    _load_dotenv()

    env_config = os.getenv("QUIZ_RELAY_CONFIG", "").strip()
    selected_path = Path(config_path).expanduser() if config_path else _path(env_config)
    data = _read_toml(selected_path)

    app_data = _section(data, "app")
    screenshot_data = _section(data, "screenshot")
    ai_data = _section(data, "ai")
    esp32_data = _section(data, "esp32")
    mouse_data = _section(data, "mouse_trigger")
    logging_data = _section(data, "logging")

    selected_profile = profile or os.getenv("QUIZ_RELAY_PROFILE") or app_data.get("profile", "default")
    app = AppConfig(
        name=str(app_data.get("name", "Quiz Relay")),
        profile=str(selected_profile),
        runtime_directory=Path(app_data.get("runtime_directory", "runtime")),
        save_screenshots=bool(app_data.get("save_screenshots", True)),
        save_ai_raw_response=bool(app_data.get("save_ai_raw_response", True)),
        allow_parallel_runs=bool(app_data.get("allow_parallel_runs", False)),
        minimum_seconds_between_runs=float(app_data.get("minimum_seconds_between_runs", 1.5)),
    )
    screenshot = ScreenshotConfig(
        backend=str(screenshot_data.get("backend", "mss")).lower(),
        format=str(screenshot_data.get("format", "png")).lower(),
        delay_ms=int(screenshot_data.get("delay_ms", 0)),
        monitor=int(screenshot_data.get("monitor", 1)),
        region=str(screenshot_data.get("region", "full")),
        preprocess=bool(screenshot_data.get("preprocess", False)),
    )
    ai = AiConfig(
        provider=str(ai_data.get("provider", "openai")).lower(),
        model=str(ai_data.get("model", "gpt-4.1-mini")),
        timeout_seconds=float(ai_data.get("timeout_seconds", 30)),
        response_language=str(ai_data.get("response_language", "de")),
        strict_json=bool(ai_data.get("strict_json", True)),
        prompt_file=_path(ai_data.get("prompt_file", ".prompt")),
        openai_image_detail=str(ai_data.get("openai_image_detail", "auto")),
        max_tokens=int(ai_data.get("max_tokens", 1024)),
    )
    esp32 = Esp32Config(
        enabled=bool(esp32_data.get("enabled", False)),
        base_url=str(esp32_data.get("base_url", "http://192.168.178.55")).rstrip("/"),
        endpoint=str(esp32_data.get("endpoint", "/solution")),
        timeout_seconds=float(esp32_data.get("timeout_seconds", 2.0)),
        retries=int(esp32_data.get("retries", 2)),
        send_explanation=bool(esp32_data.get("send_explanation", False)),
    )
    mouse = MouseTriggerConfig(
        enabled=bool(mouse_data.get("enabled", True)),
        event=str(mouse_data.get("event", "middle-click")),
        debounce_ms=int(mouse_data.get("debounce_ms", 750)),
        ignore_while_running=bool(mouse_data.get("ignore_while_running", True)),
    )
    logging = LoggingConfig(
        level=str(logging_data.get("level", "INFO")),
        runs_file=Path(logging_data.get("runs_file", "runtime/logs/runs.jsonl")),
        app_log_file=Path(logging_data.get("app_log_file", "runtime/logs/app.log")),
        error_log_file=Path(logging_data.get("error_log_file", "runtime/logs/errors.log")),
    )

    if screenshot.format != "png":
        raise ConfigurationError("Initial wird nur Screenshot-Format 'png' unterstuetzt.")
    if esp32.retries < 0:
        raise ConfigurationError("esp32.retries darf nicht negativ sein.")
    return Settings(app, screenshot, ai, esp32, mouse, logging, selected_path)
