from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Solution:
    raw: dict[str, Any]

    @classmethod
    def from_raw(cls, data: dict[str, Any]) -> "Solution":
        return cls(raw=data)

    def to_dict(self) -> dict[str, Any]:
        return self.raw

    @property
    def all_answer_ids(self) -> list[str]:
        ids: list[str] = []
        for q in self.raw.get("answers", []):
            if not isinstance(q, dict):
                continue
            for a in q.get("answers", []):
                if isinstance(a, str):
                    ids.append(a.strip().upper())
        return ids


_PULSE_TABLE = {letter: i for i, letter in enumerate("ABCDEFGHI", 1)} | {str(i): i for i in range(1, 10)}


def answers_to_pulses(answer_ids: list[str]) -> list[int]:
    return [_PULSE_TABLE[a] for a in answer_ids if a in _PULSE_TABLE]
