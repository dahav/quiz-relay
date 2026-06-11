from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_DIR = Path("runtime/logs")
WEB_LOG = LOG_DIR / "web.jsonl"


def web_log_path(upload_dir: Path) -> Path:
    return upload_dir.parent / "logs" / "web.jsonl"


def log_event(event: str, payload: dict[str, Any], path: Path = WEB_LOG) -> None:
    record = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event": event,
        **payload,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except OSError as exc:
        print(f"runtime log failed: {exc}", file=sys.stderr, flush=True)
