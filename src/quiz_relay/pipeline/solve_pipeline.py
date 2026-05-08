from __future__ import annotations

from pathlib import Path

from quiz_relay.errors import QuizRelayError, RunAlreadyActiveError
from quiz_relay.pipeline.locking import PipelineLock
from quiz_relay.pipeline.result_models import PipelineResult
from quiz_relay.pipeline.run_context import RunContext
from quiz_relay.screenshot.monitor_models import ScreenshotResult


class SolvePipeline:
    def __init__(
        self,
        screenshot_service,
        ai_solver_client,
        response_parser,
        solution_validator,
        esp32_client,
        run_logger,
        lock: PipelineLock,
        config_profile: str = "default",
    ) -> None:
        self.screenshot_service = screenshot_service
        self.ai_solver_client = ai_solver_client
        self.response_parser = response_parser
        self.solution_validator = solution_validator
        self.esp32_client = esp32_client
        self.run_logger = run_logger
        self.lock = lock
        self.config_profile = config_profile

    def run(self, source: str = "cli", test_image: Path | None = None) -> PipelineResult:
        context = RunContext.create(source=source, config_profile=self.config_profile)
        screenshot: ScreenshotResult | None = None

        try:
            self.lock.acquire(context)
        except RunAlreadyActiveError as exc:
            result = PipelineResult.locked(context, exc)
            self.run_logger.write(result)
            return result

        try:
            if test_image is None:
                screenshot = self.screenshot_service.capture(context)
            else:
                screenshot = self.screenshot_service.from_file(test_image)
            raw_response = self.ai_solver_client.solve_image(screenshot, context)
            solution = self.response_parser.parse(raw_response)
            solution = self.solution_validator.validate(solution)
            esp32_result = self.esp32_client.send_solution(context, solution)
            if esp32_result.sent or esp32_result.error == "disabled":
                result = PipelineResult.success(context, screenshot, solution, esp32_result)
            else:
                result = PipelineResult.partial(context, screenshot, solution, esp32_result)
            self.run_logger.write(result)
            return result
        except QuizRelayError as exc:
            result = PipelineResult.failed(context, exc, screenshot=screenshot)
            self.run_logger.write(result)
            return result
        finally:
            self.lock.release()
