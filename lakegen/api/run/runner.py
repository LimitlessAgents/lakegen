from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

import threading

from lakegen.agent import StopReason


class AgentEventType(StrEnum):
    TEXT_DELTA = "text_delta"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TURN_DONE = "turn_done"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class AgentEvent:
    type: AgentEventType
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type.value, "data": self.data}


@dataclass(frozen=True, slots=True)
class TurnResult:
    final_message: str
    stop_reason: StopReason


@runtime_checkable
class AgentRunner(Protocol):
    def create_session(self, *, owner_id: str) -> str: ...

    def delete_session(self, session_id: str, *, owner_id: str) -> None: ...

    def run_turn(
        self,
        session_id: str,
        user_text: str,
        *,
        owner_id: str,
        catalog_name: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        on_event: Callable[[AgentEvent], None] | None = None,
        cancel_event: threading.Event,
    ) -> TurnResult: ...
