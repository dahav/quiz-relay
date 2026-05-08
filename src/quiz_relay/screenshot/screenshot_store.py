from __future__ import annotations

from pathlib import Path

from quiz_relay.pipeline.run_context import RunContext


class ScreenshotStore:
    def __init__(self, screenshots_dir: Path) -> None:
        self.screenshots_dir = screenshots_dir

    def path_for(self, context: RunContext) -> Path:
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        return self.screenshots_dir / f"{context.task_id}.png"
