from __future__ import annotations

import json
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO


@dataclass(frozen=True)
class DebugSink:
    enabled: bool = False
    stream: TextIO = sys.stderr
    log_path: Path | None = None

    def line(self, message: str) -> None:
        if self.enabled:
            self._write(message)

    def json(self, data: Any) -> None:
        if self.enabled:
            self._write(json.dumps(data, ensure_ascii=False, indent=2))

    def exception(self, message: str, exc: BaseException) -> None:
        if self.enabled:
            self._write(message)
            self._write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip())

    def _write(self, message: str) -> None:
        print(message, file=self.stream, flush=True)
        if self.log_path is None:
            return
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                print(message, file=handle, flush=True)
        except OSError:
            pass
