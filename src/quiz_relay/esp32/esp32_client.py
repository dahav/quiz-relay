from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from quiz_relay.ai.models import AiSolution
from quiz_relay.config import Esp32Config
from quiz_relay.esp32.models import Esp32SendResult
from quiz_relay.esp32.payload_builder import Esp32PayloadBuilder
from quiz_relay.pipeline.run_context import RunContext


class Esp32Client:
    def __init__(self, config: Esp32Config, payload_builder: Esp32PayloadBuilder) -> None:
        self.config = config
        self.payload_builder = payload_builder

    def send_solution(self, context: RunContext, solution: AiSolution) -> Esp32SendResult:
        if not self.config.enabled:
            return Esp32SendResult.disabled()

        payload = self.payload_builder.build(context, solution)
        body = json.dumps(payload).encode("utf-8")
        url = f"{self.config.base_url}{self.config.endpoint}"
        attempts = self.config.retries + 1
        last_error = None
        started = time.monotonic()

        for attempt in range(attempts):
            request = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                    response_body = response.read().decode("utf-8", errors="replace")
                    duration_ms = int((time.monotonic() - started) * 1000)
                    return Esp32SendResult(
                        sent=200 <= response.status < 300,
                        status_code=response.status,
                        response_body=response_body,
                        duration_ms=duration_ms,
                        error=None if 200 <= response.status < 300 else f"HTTP {response.status}",
                    )
            except urllib.error.HTTPError as exc:
                body_text = exc.read().decode("utf-8", errors="replace")
                if 400 <= exc.code < 500:
                    return Esp32SendResult(False, exc.code, body_text, int((time.monotonic() - started) * 1000), f"HTTP {exc.code}")
                last_error = f"HTTP {exc.code}: {body_text}"
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = str(exc)
            if attempt + 1 < attempts:
                time.sleep(0.1)

        return Esp32SendResult(
            sent=False,
            status_code=None,
            response_body=None,
            duration_ms=int((time.monotonic() - started) * 1000),
            error=last_error or "ESP32-Versand fehlgeschlagen",
        )
