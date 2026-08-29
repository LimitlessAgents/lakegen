from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

from lakegen.agent import AgentConfig, AgentLoop
from lakegen.agent.serialization import serialize_agent_loop_result
from lakegen.core.catalog.service import catalog_service
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.inference import StreamChunk
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
        self._tools = ToolRuntime(registry=self.env.tool_registry)
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
        with self._lock:
            self._ensure_open()
            turn_id = str(uuid.uuid4())
            switched_from: str | None = None
            effective_catalog = catalog_name if catalog_name is not None else self.state.catalog_name
            if effective_catalog is None:
                raise BaseError(
                    ErrorCode.INVALID_ARGUMENT,
                    "catalog_name is required.",
                )
            if catalog_name is not None and catalog_name != self.state.catalog_name:
                catalog_service.require(catalog_name)
                switched_from = self.state.catalog_name
                self.state.catalog_name = catalog_name
            elif self.state.catalog_name is None:
                catalog_service.require(effective_catalog)
                self.state.catalog_name = effective_catalog

            base = self.state.config
            agent_config = AgentConfig(
                model=model if model is not None else base.model,
                system_prompt=base.system_prompt,
                provider=provider if provider is not None else base.provider,
                max_turns=base.max_turns,
            )
            loop_result = self._loop.invoke(
                agent_config=agent_config,
                conversation=self.state.messages,
                user_text=user_text,
                catalog_name=self.state.catalog_name,
                catalog_switched_from=switched_from,
                stream=stream,
                on_chunk=on_chunk,
                cancel_event=(
                    cancel_event
                    if cancel_event is not None
                    else threading.Event()
                ),
            )

            self.env.persistence.store_turn(
                session_id=self.id,
                turn_id=turn_id,
                result=serialize_agent_loop_result(loop_result),
            )
            self.state.messages.messages.extend(loop_result.turn_messages.messages)
            return SessionTurnResult(id=turn_id, result=loop_result)

    def spawn(self, config: AgentConfig) -> Session:
        """Create a child session that shares this session's Environment."""
        with self._lock:
            self._ensure_open()
            if self._manager is None:
                raise RuntimeError(
                    "Session has no manager; create sessions via SessionManager."
                )
        return self._manager.create(
            config,
            owner_id=self.state.owner_id,
            parent_id=self.id,
        )

    def close(self) -> None:
        with self._lock:
            self.state.closed = True
