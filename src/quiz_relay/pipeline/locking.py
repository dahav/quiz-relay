from __future__ import annotations

import fcntl
from pathlib import Path

from quiz_relay.errors import RunAlreadyActiveError
from quiz_relay.pipeline.run_context import RunContext


class PipelineLock:
    def __init__(self, lock_path: Path, allow_parallel_runs: bool = False) -> None:
        self.lock_path = lock_path
        self.allow_parallel_runs = allow_parallel_runs
        self._file = None

    def acquire(self, context: RunContext) -> bool:
        if self.allow_parallel_runs:
            return True
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.lock_path.open("w", encoding="utf-8")
        try:
            fcntl.flock(self._file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._file.close()
            self._file = None
            raise RunAlreadyActiveError("Ein Pipeline-Run ist bereits aktiv.") from exc
        self._file.write(f"{context.task_id}\n")
        self._file.flush()
        return True

    def release(self) -> None:
        if self.allow_parallel_runs or self._file is None:
            return
        fcntl.flock(self._file, fcntl.LOCK_UN)
        self._file.close()
        self._file = None
