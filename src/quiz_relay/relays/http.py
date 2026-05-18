from __future__ import annotations

import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from quiz_relay.relays.base import Relay


@dataclass(frozen=True)
class HttpRelay(Relay):
    name = "http"

    url: str
    timeout_seconds: float
    on: int
    off: int
    pause: int
    duty: int

    @classmethod
    def from_config(cls, section: dict[str, Any]) -> "HttpRelay":
        url = section.get("url")
        if not url:
            raise SystemExit("[relay.http] url is required.")
        return cls(
            url=str(url),
            timeout_seconds=float(section.get("timeout_seconds", 2.0)),
            on=int(section.get("on", 300)),
            off=int(section.get("off", 200)),
            pause=int(section.get("pause", 800)),
            duty=int(section.get("duty", 170)),
        )

    def send(self, pulses: list[int]) -> dict[str, Any]:
        if not pulses:
            print("relay[http] no pulses to send", file=sys.stderr, flush=True)
            return {"sent": False, "error": "no pulses"}

        params: dict[str, str] = {
            "on": str(self.on),
            "off": str(self.off),
            "pause": str(self.pause),
            "duty": str(self.duty),
        }
        if len(pulses) == 1:
            params["n"] = str(pulses[0])
        else:
            params["seq"] = ",".join(str(p) for p in pulses[:8])

        sep = "&" if urllib.parse.urlparse(self.url).query else "?"
        full_url = f"{self.url}{sep}{urllib.parse.urlencode(params)}"
        print(f"relay[http] GET {full_url}", file=sys.stderr, flush=True)
        try:
            with urllib.request.urlopen(full_url, timeout=self.timeout_seconds) as response:
                print(f"relay[http] <- {response.status}", file=sys.stderr, flush=True)
                return {"sent": 200 <= response.status < 300, "status": response.status}
        except Exception as exc:
            print(f"relay[http] error: {exc}", file=sys.stderr, flush=True)
            return {"sent": False, "error": str(exc)}
