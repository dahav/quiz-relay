from __future__ import annotations

import getpass
import socket
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime


def _task_timestamp(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H-%M-%S.%f")[:-3] + "Z"


@dataclass(frozen=True)
class RunContext:
    task_id: str
    source: str
    started_at: datetime
    host: str | None
    user: str | None
    config_profile: str

    @classmethod
    def create(cls, source: str, config_profile: str = "default") -> "RunContext":
        started_at = datetime.now(UTC)
        suffix = uuid.uuid4().hex[:4]
        return cls(
            task_id=f"{_task_timestamp(started_at)}-{suffix}",
            source=source,
            started_at=started_at,
            host=socket.gethostname(),
            user=getpass.getuser(),
            config_profile=config_profile,
        )

    def started_iso(self) -> str:
        return self.started_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
