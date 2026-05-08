from __future__ import annotations

import base64
from pathlib import Path
from typing import Protocol

from quiz_relay.config import AiConfig
from quiz_relay.errors import AiRequestError
from quiz_relay.screenshot.monitor_models import ScreenshotResult


class VisionProvider(Protocol):
    name: str

    def analyze(self, image: ScreenshotResult, prompt: str) -> str:
        ...


class OpenAiVisionProvider:
    name = "openai"

    def __init__(self, config: AiConfig) -> None:
        self.config = config

    def analyze(self, image: ScreenshotResult, prompt: str) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AiRequestError("Das Python-Paket 'openai' ist nicht installiert.") from exc

        image_path = Path(image.path)
        image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
        try:
            client = OpenAI(timeout=self.config.timeout_seconds)
            response = client.responses.create(
                model=self.config.model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {
                                "type": "input_image",
                                "image_url": f"data:{image.mime_type};base64,{image_data}",
                                "detail": self.config.openai_image_detail,
                            },
                        ],
                    }
                ],
            )
            return response.output_text.strip()
        except Exception as exc:
            raise AiRequestError(f"OpenAI-Anfrage fehlgeschlagen: {exc}") from exc


class AnthropicVisionProvider:
    name = "anthropic"

    def __init__(self, config: AiConfig) -> None:
        self.config = config

    def analyze(self, image: ScreenshotResult, prompt: str) -> str:
        try:
            import anthropic
        except ImportError as exc:
            raise AiRequestError("Das Python-Paket 'anthropic' ist nicht installiert.") from exc

        image_path = Path(image.path)
        image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
        try:
            client = anthropic.Anthropic(timeout=self.config.timeout_seconds)
            message = client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
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
            return "\n".join(
                block.text for block in message.content if getattr(block, "type", None) == "text"
            ).strip()
        except Exception as exc:
            raise AiRequestError(f"Anthropic-Anfrage fehlgeschlagen: {exc}") from exc


def create_provider(config: AiConfig) -> VisionProvider:
    provider = config.provider.lower()
    if provider in {"openai", "chatgpt"}:
        return OpenAiVisionProvider(config)
    if provider in {"anthropic", "claude"}:
        return AnthropicVisionProvider(config)
    raise AiRequestError(f"Unbekannter KI-Provider: {config.provider}")
