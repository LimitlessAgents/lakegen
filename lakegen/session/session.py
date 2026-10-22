from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

from lakegen.agent import (
    AgentConfig,
    AgentLoop,
    AgentLoopFailure,
    AgentLoopResult,
)
from lakegen.agent.serialization import serialize_agent_loop_result
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.inference import StreamChunk
from lakegen.session.compaction import compact
from lakegen.session.environment import Environment
from lakegen.session.model import SessionState, SessionTurnResult
from lakegen.tool import ToolRuntime

if TYPE_CHECKING:
    from lakegen.session.manager import SessionManager


class Session:
    """One conversation thread: owns context, uses a shared Environment."""

    def __init__(
        self,
        state: SessionState,
        env: Environment | None = None,
        manager: SessionManager | None = None,
    ) -> None:
        self.state = state
        self.env = env if env is not None else Environment.default()
        self._manager = manager
        self._lock = threading.Lock()
        self._tools = ToolRuntime(
            registry=self.env.tool_registry,
            catalogs=self.env.catalog_service,
        )
        self._loop = AgentLoop(
            router=self.env.inference_router,
            tool_runtime=self._tools,
        )

    @property
    def id(self) -> str:
        return self.state.id

    @property
    def parent_id(self) -> str | None:
        return self.state.parent_id

    def _ensure_open(self) -> None:
        if self.state.closed:
            raise BaseError(
                ErrorCode.NOT_FOUND,
                f"Session {self.id!r} is closed.",
            )
        if self._manager is not None:
            if self.id in self._manager._deleting:
                raise BaseError(
                    ErrorCode.NOT_FOUND,
                    f"Session {self.id!r} not found.",
                )
            if not self.env.session_repository.exists(self.id):
                raise BaseError(
                    ErrorCode.NOT_FOUND,
                    f"Session {self.id!r} not found.",
                )
            cached = self._manager._cache.get(self.id)
            if cached is not None and cached is not self:
                raise BaseError(
                    ErrorCode.NOT_FOUND,
                    f"Session {self.id!r} not found.",
                )

    def _resolve_catalog(self, catalog_name: str | None) -> str:
        stored = self.state.catalog_name
        if stored is not None:
            if catalog_name is not None and catalog_name != stored:
                raise BaseError(
                    ErrorCode.INVALID_ARGUMENT,
                    "Session catalog cannot be changed.",
                )
            return stored
        if catalog_name is None:
            raise BaseError(
                ErrorCode.INVALID_ARGUMENT,
                "catalog_name is required.",
            )
        self.env.catalog_service.require(catalog_name)
        self.env.session_repository.set_catalog_name(self.id, catalog_name)
        self.state.catalog_name = catalog_name
        return catalog_name

    def send(
        self,
        user_text: str,
        *,
        catalog_name: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        stream: bool = False,
        on_chunk: Callable[[StreamChunk], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> SessionTurnResult:
        """Run one user turn. Serialized per session so messages stay consistent.

        ``catalog_name`` is required on the first turn if the session has none yet.
        ``model`` and ``provider`` apply to this turn only.
        """
        if self._manager is not None:
            self._manager.pin_session(self.id)
        try:
            with self._lock:
                self._ensure_open()
                turn_id = str(uuid.uuid4())
                effective_catalog = self._resolve_catalog(catalog_name)

                base = self.state.config
                agent_config = AgentConfig(
                    model=model if model is not None else base.model,
                    system_prompt=base.system_prompt,
                    provider=provider if provider is not None else base.provider,
                    max_turns=base.max_turns,
                    # Endpoint is session-level like the system prompt: a turn may
                    # change model/provider but not which API the session talks to.
                    base_url=base.base_url,
                )
                try:
                    loop_result = self._loop.invoke(
                        agent_config=agent_config,
                        conversation=self.state.messages,
                        user_text=user_text,
                        catalog_name=effective_catalog,
                        catalog_switched_from=None,
                        stream=stream,
                        on_chunk=on_chunk,
                        cancel_event=(
                            cancel_event
                            if cancel_event is not None
                            else threading.Event()
                        ),
                    )
                except AgentLoopFailure as failure:
                    self._persist_and_commit_turn(turn_id, failure.result)
                    raise failure.error.with_traceback(
                        failure.error.__traceback__
                    ) from None

                self._persist_and_commit_turn(turn_id, loop_result)

                try:
                    state_copy = list(self.state.messages.messages)

                    # Run compaction if required
                    if self._check_if_compaction_needed():
                        # Run compaction with the compaction model, defaulting to the base model if not set
                        compaction_model = os.getenv("COMPACTION_MODEL", None) or base.model
                        compaction_result = compact(
                            inference_router=self.env.inference_router,
                            provider=provider if provider is not None else base.provider,
                            model=compaction_model,
                            conversation=self.state.messages,
                            # Summarise through the endpoint the session talks to, so an
                            # OPENAI_BASE_URL override covers compaction too.
                            base_url=base.base_url,
                            cancel_event=(
                                cancel_event
                                if cancel_event is not None
                                else threading.Event()
                            ),
                        )

                        if compaction_result.content.strip():
                            # Replace context with compacted summary
                            self.state.messages.messages = [compaction_result]

                            # Persist in database
                            self._persist_and_commit_compaction(
                                compaction_id=str(uuid.uuid4()),
                                compacted_data=compaction_result.content,
                                last_compacted_turn_id=turn_id,
                            )

                except Exception:
                    # TODO(compaction observability): this swallows every
                    # compaction failure so it can't break an otherwise-successful
                    # turn, which also hides the cause — e.g. the OpenAI provider
                    # 400s when `tools` is sent as null, silently disabling
                    # compaction, and an empty summary is dropped by the guard
                    # above. Log the exception and emit a metric in a follow-up PR.
                    self.state.messages.messages = state_copy

                return SessionTurnResult(id=turn_id, result=loop_result)
        finally:
            if self._manager is not None:
                self._manager.unpin_session(self.id)

    def _persist_and_commit_turn(
        self,
        turn_id: str,
        loop_result: AgentLoopResult,
    ) -> None:
        self.env.agent_turn_repository.create(
            {
                "id": turn_id,
                "session_id": self.id,
                "result": serialize_agent_loop_result(loop_result),
            }
        )
        self.state.messages.messages.extend(loop_result.turn_messages.messages)

    def _persist_and_commit_compaction(
        self,
        compaction_id: str,
        compacted_data: str,
        last_compacted_turn_id: str,
    ) -> None:
        self.env.compaction_repository.create(
            {
                "id": compaction_id,
                "data": compacted_data,
                "session_id": self.id,
                "last_compacted_turn_id": last_compacted_turn_id,
            }
        )

    def spawn(self, config: AgentConfig) -> str:
        """Create a child session that shares this session's Environment.

        Returns the child session id; use :meth:`SessionManager.get` before use.
        """
        with self._lock:
            self._ensure_open()
            if self._manager is None:
                raise RuntimeError(
                    "Session has no manager; create sessions via SessionManager."
                )
            manager = self._manager
        return manager.create(
            config,
            owner_id=self.state.owner_id,
            parent_id=self.id,
        )

    def _check_if_compaction_needed(self) -> bool:
        # Count all message text (including tool output) as ~4 chars/token.
        char_count = sum(
            len(msg.content or "") for msg in self.state.messages.messages
        )
        token_count = char_count // 4  # Assuming ~4 chars as one token
        return token_count > self.env.token_budget.conversation * 0.7

    def close(self) -> bool:
        """Close the session and return whether it was already closed."""
        with self._lock:
            was_closed = self.state.closed
            self.state.closed = True
            return was_closed

    def _reopen(self) -> None:
        with self._lock:
            self.state.closed = False
