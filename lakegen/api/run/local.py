from __future__ import annotations

from collections.abc import Callable

import threading

from lakegen.api.run.runner import AgentEvent, AgentEventType, TurnResult
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.inference import StreamChunk
from lakegen.session import Session, SessionManager
from lakegen.session.environment import Environment


class LocalRunAdapter:
    """In-process AgentRunner backed by ``SessionManager``."""

    def __init__(
        self,
        manager: SessionManager | None = None,
        *,
        env: Environment | None = None,
    ) -> None:
        self._manager = manager if manager is not None else SessionManager(env=env)

    @property
    def manager(self) -> SessionManager:
        return self._manager

    def create_session(self, *, owner_id: str) -> str:
        session = self._manager.create(owner_id=owner_id)
        return session.id

    def delete_session(self, session_id: str, *, owner_id: str) -> None:
        self._require_owner(session_id, owner_id)
        self._manager.delete(session_id)

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
    ) -> TurnResult:
        session = self._require_owner(session_id, owner_id)

        def _on_chunk(chunk: StreamChunk) -> None:
            if on_event is None or cancel_event.is_set():
                return
            if chunk.text:
                on_event(
                    AgentEvent(
                        type=AgentEventType.TEXT_DELTA,
                        data={"text": chunk.text},
                    )
                )

        result = session.send(
            user_text,
            catalog_name=catalog_name,
            model=model,
            provider=provider,
            stream=True,
            on_chunk=_on_chunk,
            cancel_event=cancel_event
        )

        turn = TurnResult(
            final_message=result.final_message,
            stop_reason=result.stop_reason,
        )
        if on_event is not None:
            on_event(
                AgentEvent(
                    type=AgentEventType.TURN_DONE,
                    data={
                        "final_message": turn.final_message,
                        "stop_reason": turn.stop_reason.value,
                    },
                )
            )
        return turn

    def _require_owner(self, session_id: str, owner_id: str) -> Session:
        session = self._manager.get(session_id)
        if session.state.owner_id != owner_id:
            raise BaseError(
                ErrorCode.NOT_FOUND,
                f"Session {session_id!r} not found.",
            )
        return session
