from dataclasses import replace
from datetime import datetime
from pathlib import Path
import re

from quiz_relay.config import load_settings
from quiz_relay.models import AiRawResponse, RelaySendResult, ScreenshotResult
from quiz_relay.runner import run_once, run_record


class LoggerStub:
    def __init__(self):
        self.records = []

    def write(self, settings, result):
        self.records.append(result)


class CaptureStub:
    def __init__(self):
        self.called = False

    def __call__(self, settings, context):
        self.called = True
        return ScreenshotResult(path="/tmp/test.png")


def solve_stub(image, settings, base_dir):
    return AiRawResponse(
        """
        {
          "explanation": "ok",
          "answers": [
            {
              "question": 1,
              "question_text": "Choose the letter A.",
              "options": [
                {"id": "A", "text": "The letter A"},
                {"id": "B", "text": "The letter B"}
              ],
              "answers": ["a"]
            }
          ],
          "confidence": 0.8
        }
        """,
        "test",
        "test",
    )


def relay_stub(settings, context, solution):
    return RelaySendResult(True, 200, "ok", 1)


def make_settings(tmp_path: Path):
    settings = load_settings(None)
    return replace(
        settings,
        app=replace(settings.app, runtime_directory=tmp_path),
        logging=replace(settings.logging, runs_file=tmp_path / "runs.jsonl"),
    )


def test_run_success(tmp_path: Path):
    settings = make_settings(tmp_path)
    capture = CaptureStub()
    logger = LoggerStub()
    result = run_once(
        settings,
        capture=capture,
        analyze=solve_stub,
        send=relay_stub,
        write_log=logger.write,
    )
    assert result.status == "success"
    assert capture.called is True
    assert result.solution.answers[0].answers == ["A"]
    assert logger.records == [result]
    record = run_record(settings, result)
    assert datetime.fromisoformat(record["started_at"]).utcoffset() is not None
    assert datetime.fromisoformat(record["finished_at"]).utcoffset() is not None
    assert not record["started_at"].endswith("Z")
    assert not record["finished_at"].endswith("Z")
    assert re.search(r"T\d{2}-\d{2}-\d{2}\.\d{3}[+-]\d{4}-[0-9a-f]{4}$", record["task_id"])
    assert record["answers"][0]["question_text"] == "Choose the letter A."
    assert record["answers"][0]["options"] == [
        {"id": "A", "text": "The letter A"},
        {"id": "B", "text": "The letter B"},
    ]


def test_run_test_image_skips_capture(tmp_path: Path):
    image = tmp_path / "image.png"
    image.write_bytes(b"png")
    capture = CaptureStub()
    result = run_once(
        make_settings(tmp_path),
        test_image=image,
        capture=capture,
        analyze=solve_stub,
        send=relay_stub,
        write_log=LoggerStub().write,
    )
    assert result.status == "success"
    assert capture.called is False
