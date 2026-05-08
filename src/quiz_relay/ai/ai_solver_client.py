from __future__ import annotations

from quiz_relay.ai.models import AiRawResponse
from quiz_relay.pipeline.run_context import RunContext
from quiz_relay.screenshot.monitor_models import ScreenshotResult


class AiSolverClient:
    def __init__(self, provider, prompt_builder, model: str) -> None:
        self.provider = provider
        self.prompt_builder = prompt_builder
        self.model = model

    def solve_image(self, image: ScreenshotResult, context: RunContext) -> AiRawResponse:
        prompt = self.prompt_builder.build()
        text = self.provider.analyze(image, prompt)
        return AiRawResponse(text=text, provider=self.provider.name, model=self.model)
