from __future__ import annotations

import os
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from lakegen.agent import (
    AgentConfig,
    AgentLoop,
    AgentLoopFailure,
    AgentLoopResult,
    Conversation,
)
from lakegen.agent.model import CompressionScope
from lakegen.agent.serialization import serialize_agent_loop_result
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.inference import StreamChunk
from lakegen.session.environment import Environment
from lakegen.session.model import SessionState, SessionTurnResult
from lakegen.tool import ToolDefinition, ToolRuntime

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

                self._compress_history(
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
                        context_policy=self.env.context_policy,
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
                return SessionTurnResult(id=turn_id, result=loop_result)
        finally:
            if self._manager is not None:
                self._manager.unpin_session(self.id)

    def _persist_result(
        self,
        loop_result: AgentLoopResult,
        agent_config: AgentConfig,
        system_prompt: str,
        tools: list[ToolDefinition],
        cancel_event: threading.Event,
    ) -> int:
        completed = Conversation(
            messages=[
                *self.state.messages.messages,
                *loop_result.turn_messages.messages,
            ]
        )
        measurement = self.env.context_engine.measure(
            history=completed,
            system_prompt=system_prompt,
            tools=tools,
        )
        turn_id = self._persist_turn(
            loop_result,
            context_tokens=measurement.total,
            context_source=measurement.source,
        )

        self.state.messages.messages.extend(loop_result.turn_messages.messages)
        self._compress_history(
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
        context_tokens: int | None = None,
        context_source: str | None = None,
        connection: psycopg.Connection | None = None,
    ) -> int:
        # Raw turn messages are canonical history and the eval record. Turn
        # compressions live alongside them as events, never as replacement
        # history.
        return self.env.agent_turn_repository.create(
            {
                "session_id": self.id,
                "result": serialize_agent_loop_result(result),
                "context_tokens": context_tokens,
                "context_source": context_source,
            },
            connection=connection,
        )

    def _compress_history(
        self,
        agent_config: AgentConfig,
        system_prompt: str,
        tools: list[ToolDefinition],
        cancel_event: threading.Event,
        *,
        last_turn_id: int | None = None,
    ) -> None:
        if last_turn_id is None:
            last_turn_id = self.env.agent_turn_repository.latest_id(self.id)
        if last_turn_id is None:
            return

        try:
            policy = self.env.context_policy
            measurement = self.env.context_engine.measure(
                history=self.state.messages,
                system_prompt=system_prompt,
                tools=tools,
            )
            if measurement.total < policy.history_limit:
                return

            compression = self.env.context_engine.compress(
                CompressionScope.HISTORY,
                self.state.messages,
                router=self.env.inference_router,
                provider=agent_config.provider,
                model=os.getenv("COMPRESSION_MODEL") or agent_config.model,
                cancel_event=cancel_event,
                base_url=agent_config.base_url,
            )
            if compression is None:
                return

            after = self.env.context_engine.measure(
                history=compression.messages,
                system_prompt=system_prompt,
                tools=tools,
            )
            if after.total >= measurement.total:
                return  # no progress; retry at the next turn boundary

            self.env.agent_turn_repository.update_summary(
                last_turn_id,
                summary=compression.summary.content or "",
                summary_kind=CompressionScope.HISTORY.value,
                context_tokens=after.total,
                context_source=after.source,
            )
            self.state.messages = compression.messages
        except Exception:
            # Compression must never break an otherwise-successful turn. The
            # raw history stays intact and the next gate retries.
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
