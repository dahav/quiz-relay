from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from quiz_relay.config import Settings
from quiz_relay.errors import AuditWriteError
from quiz_relay.pipeline.result_models import PipelineResult


class RunLogger:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.runs_file = settings.logging.runs_file

    def write(self, result: PipelineResult) -> None:
        record = self._record(result)
        try:
            self.runs_file.parent.mkdir(parents=True, exist_ok=True)
            with self.runs_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            raise AuditWriteError(f"Audit-Datensatz konnte nicht geschrieben werden: {exc}") from exc

    def _record(self, result: PipelineResult) -> dict[str, Any]:
        context = result.context
        record: dict[str, Any] = {
            "task_id": context.task_id,
            "source": context.source,
            "started_at": context.started_iso(),
            "finished_at": result.finished_at.isoformat().replace("+00:00", "Z"),
            "duration_ms": result.duration_ms,
            "host": context.host,
            "user": context.user,
            "config_profile": context.config_profile,
            "status": result.status,
        }
        if result.screenshot:
            record["screenshot_path"] = result.screenshot.path
        if result.solution:
            record["explanation"] = result.solution.explanation
            record["answers"] = [
                {"question": item.question, "answers": item.answers}
                for item in result.solution.answers
            ]
            record["confidence"] = result.solution.confidence
            if self.settings.app.save_ai_raw_response:
                record["ai_raw_response"] = result.solution.raw_response
        if result.esp32_result:
            record["esp32"] = {
                "sent": result.esp32_result.sent,
                "status_code": result.esp32_result.status_code,
                "response_body": result.esp32_result.response_body,
                "duration_ms": result.esp32_result.duration_ms,
                "error": result.esp32_result.error,
            }
        if result.error:
            record["error_stage"] = result.error.stage
            record["error_type"] = result.error.error_type
            record["error_message"] = result.error.message
        return record
