from __future__ import annotations

import os
import threading
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING

from lakegen.agent import (
    AgentConfig,
    AgentLoop,
    AgentLoopFailure,
    AgentLoopResult,
    Conversation,
)
from lakegen.agent.serialization import serialize_agent_loop_result
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.inference import StreamChunk
from lakegen.session.environment import Environment
from lakegen.session.model import SessionState, SessionTurnResult
from lakegen.tool import ToolRuntime

if TYPE_CHECKING:
    import psycopg

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
            context_engine=self.env.context_engine,
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
                cancel = cancel_event if cancel_event is not None else threading.Event()
                system_prompt = self._loop._build_prompt(
                    agent_config,
                    effective_catalog,
                )
                tools = self._tools.list_definitions()

                self._compress_if_needed(
                    agent_config,
                    system_prompt,
                    tools,
                    cancel,
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
                        cancel_event=cancel,
                        context_budget=self.env.token_budget.conversation,
                    )
                except AgentLoopFailure as failure:
                    self._persist_result(
                        failure.result,
                        agent_config,
                        system_prompt,
                        tools,
                        cancel,
                    )
                    raise failure.error.with_traceback(
                        failure.error.__traceback__
                    ) from None

                turn_id = self._persist_result(
                    loop_result,
                    agent_config,
                    system_prompt,
                    tools,
                    cancel,
                )
                self.state.context_tokens = (
                    self.env.context_engine.estimate_context_tokens(
                        self.state.messages,
                        system_prompt=system_prompt,
                        tools=tools,
                    )
                )
                return SessionTurnResult(id=turn_id, result=loop_result)
        finally:
            if self._manager is not None:
                self._manager.unpin_session(self.id)

    def _persist_result(
        self,
        loop_result: AgentLoopResult,
        agent_config: AgentConfig,
        system_prompt: str,
        tools: list,
        cancel_event: threading.Event,
    ) -> int:
        turn_id = self._persist_turn(loop_result)

        if loop_result.compressed is not None:
            try:
                self._commit_compression(
                    loop_result.compressed,
                    last_turn_id=turn_id,
                )
                self.state.messages = loop_result.compressed
            except Exception:
                self.state.messages.messages.extend(loop_result.turn_messages.messages)
            return turn_id

        self.state.messages.messages.extend(loop_result.turn_messages.messages)
        self._compress_if_needed(
            agent_config,
            system_prompt,
            tools,
            cancel_event,
            last_turn_id=turn_id,
        )
        return turn_id

    def _persist_turn(
        self,
        result: AgentLoopResult,
        *,
        connection: psycopg.Connection | None = None,
    ) -> int:
        # ``compressed`` is an in-memory handoff; agent_turns only ever stores
        # the raw turn for history and evals.
        persisted = (
            replace(result, compressed=None)
            if result.compressed is not None
            else result
        )
        return self.env.agent_turn_repository.create(
            {
                "session_id": self.id,
                "result": serialize_agent_loop_result(persisted),
            },
            connection=connection,
        )

    def _commit_compression(
        self,
        conversation: Conversation,
        *,
        last_turn_id: int,
    ) -> None:
        messages = conversation.messages
        if not messages or not messages[0].is_summary:
            return

        # Only the summary and its marker are stored. The tail lives in memory
        # (and is rebuilt on hydration); raw turns are already in agent_turns.
        self.env.compression_repository.create(
            {
                "data": messages[0].content or "",
                "session_id": self.id,
                "last_compressed_turn_id": last_turn_id,
            }
        )

    def _compress_if_needed(
        self,
        agent_config: AgentConfig,
        system_prompt: str,
        tools: list,
        cancel_event: threading.Event,
        *,
        last_turn_id: int | None = None,
    ) -> None:
        if last_turn_id is None:
            last_turn_id = self.env.agent_turn_repository.latest_id(self.id)
        if last_turn_id is None:
            return

        try:
            if not self.env.context_engine.needs_compression(
                self.state.messages,
                budget_tokens=self.env.token_budget.conversation,
                system_prompt=system_prompt,
                tools=tools,
            ):
                return
            compressed = self.env.context_engine.compress(
                self.state.messages,
                budget_tokens=self.env.token_budget.conversation,
                router=self.env.inference_router,
                provider=agent_config.provider,
                model=os.getenv("COMPRESSION_MODEL") or agent_config.model,
                cancel_event=cancel_event,
                base_url=agent_config.base_url,
            )
            if compressed is self.state.messages:
                return
            self._commit_compression(compressed, last_turn_id=last_turn_id)
            self.state.messages = compressed
        except Exception:
            # Compression must never break an otherwise-successful turn.
            return

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

    def close(self) -> bool:
        """Close the session and return whether it was already closed."""
        with self._lock:
            was_closed = self.state.closed
            self.state.closed = True
            return was_closed

    def _reopen(self) -> None:
        with self._lock:
            self.state.closed = False
