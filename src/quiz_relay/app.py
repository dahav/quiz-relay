from __future__ import annotations

from pathlib import Path

from quiz_relay.ai.ai_solver_client import AiSolverClient
from quiz_relay.ai.prompt_builder import PromptBuilder
from quiz_relay.ai.providers import create_provider
from quiz_relay.ai.response_parser import AiResponseParser
from quiz_relay.ai.solution_validator import SolutionValidator
from quiz_relay.audit.run_logger import RunLogger
from quiz_relay.config import Settings
from quiz_relay.errors import ConfigurationError
from quiz_relay.esp32.esp32_client import Esp32Client
from quiz_relay.esp32.payload_builder import Esp32PayloadBuilder
from quiz_relay.pipeline.locking import PipelineLock
from quiz_relay.pipeline.solve_pipeline import SolvePipeline
from quiz_relay.screenshot.backends import MssScreenshotBackend
from quiz_relay.screenshot.screenshot_service import ScreenshotService
from quiz_relay.screenshot.screenshot_store import ScreenshotStore


def build_screenshot_service(settings: Settings) -> ScreenshotService:
    if settings.screenshot.backend != "mss":
        raise ConfigurationError(f"Nicht unterstuetztes Screenshot-Backend: {settings.screenshot.backend}")
    screenshots_dir = settings.app.runtime_directory / "screenshots"
    return ScreenshotService(MssScreenshotBackend(settings.screenshot), ScreenshotStore(screenshots_dir))


def build_pipeline(settings: Settings, base_dir: Path = Path(".")) -> SolvePipeline:
    screenshot_service = build_screenshot_service(settings)
    provider = create_provider(settings.ai)
    prompt_builder = PromptBuilder(settings.ai, base_dir=base_dir)
    ai_solver = AiSolverClient(provider, prompt_builder, settings.ai.model)
    esp32_builder = Esp32PayloadBuilder(settings.esp32)
    esp32_client = Esp32Client(settings.esp32, esp32_builder)
    run_logger = RunLogger(settings)
    lock = PipelineLock(
        settings.app.runtime_directory / "quiz-relay.lock",
        allow_parallel_runs=settings.app.allow_parallel_runs,
    )
    return SolvePipeline(
        screenshot_service=screenshot_service,
        ai_solver_client=ai_solver,
        response_parser=AiResponseParser(),
        solution_validator=SolutionValidator(),
        esp32_client=esp32_client,
        run_logger=run_logger,
        lock=lock,
        config_profile=settings.app.profile,
    )
