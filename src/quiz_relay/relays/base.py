from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from quiz_relay.solution import Solution


class Relay(ABC):
    name: ClassVar[str] = ""

    @classmethod
    @abstractmethod
    def from_config(cls, section: dict[str, Any]) -> "Relay": ...

    @abstractmethod
    def send(self, solution: Solution) -> dict[str, Any]: ...
