from pathlib import Path

from quiz_relay.ai.models import AiRawResponse, AiSolution, QuestionAnswer
from quiz_relay.esp32.models import Esp32SendResult
from quiz_relay.pipeline.locking import PipelineLock
from quiz_relay.pipeline.solve_pipeline import SolvePipeline
from quiz_relay.screenshot.monitor_models import ScreenshotResult


class ScreenshotStub:
    def __init__(self):
        self.capture_called = False

    def capture(self, context):
        self.capture_called = True
        return ScreenshotResult(path="/tmp/test.png")

    def from_file(self, path: Path):
        return ScreenshotResult(path=str(path))


class AiStub:
    def solve_image(self, image, context):
        return AiRawResponse('{"explanation":"ok","answers":[{"question":1,"answers":["a"]}],"confidence":0.8}', "test", "test")


class EspStub:
    def send_solution(self, context, solution):
        return Esp32SendResult(True, 200, "ok", 1)


class LoggerStub:
    def __init__(self):
        self.records = []

    def write(self, result):
        self.records.append(result)


def test_pipeline_success(tmp_path: Path):
    screenshots = ScreenshotStub()
    logger = LoggerStub()
    pipeline = SolvePipeline(
        screenshot_service=screenshots,
        ai_solver_client=AiStub(),
        response_parser=__import__("quiz_relay.ai.response_parser", fromlist=["AiResponseParser"]).AiResponseParser(),
        solution_validator=__import__("quiz_relay.ai.solution_validator", fromlist=["SolutionValidator"]).SolutionValidator(),
        esp32_client=EspStub(),
        run_logger=logger,
        lock=PipelineLock(tmp_path / "lock"),
    )
    result = pipeline.run()
    assert result.status == "success"
    assert screenshots.capture_called is True
    assert result.solution.answers[0].answers == ["A"]
    assert logger.records == [result]


def test_pipeline_test_image_skips_capture(tmp_path: Path):
    image = tmp_path / "image.png"
    image.write_bytes(b"png")
    screenshots = ScreenshotStub()
    pipeline = SolvePipeline(
        screenshot_service=screenshots,
        ai_solver_client=AiStub(),
        response_parser=__import__("quiz_relay.ai.response_parser", fromlist=["AiResponseParser"]).AiResponseParser(),
        solution_validator=__import__("quiz_relay.ai.solution_validator", fromlist=["SolutionValidator"]).SolutionValidator(),
        esp32_client=EspStub(),
        run_logger=LoggerStub(),
        lock=PipelineLock(tmp_path / "lock"),
    )
    result = pipeline.run(test_image=image)
    assert result.status == "success"
    assert screenshots.capture_called is False
