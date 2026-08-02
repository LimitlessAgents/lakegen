from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from lakegen.agent import AgentConfig, AgentLoop, AgentLoopResult
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.inference import StreamChunk
from lakegen.session.environment import Environment
from lakegen.session.model import SessionState
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
    def id(self) -> int:
        return self.state.id

    @property
    def parent_id(self) -> int | None:
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
        stream: bool = False,
        on_chunk: Callable[[StreamChunk], None] | None = None,
    ) -> AgentLoopResult:
        """Run one user turn. Serialized per session so messages stay consistent."""
        with self._lock:
            self._ensure_open()
            return self._loop.invoke(
                agent_config=self.state.config,
                conversation=self.state.messages,
                user_text=user_text,
                stream=stream,
                on_chunk=on_chunk,
            )

    def spawn(self, config: AgentConfig) -> Session:
        """Create a child session that shares this session's Environment."""
        with self._lock:
            self._ensure_open()
            if self._manager is None:
                raise RuntimeError(
                    "Session has no manager; create sessions via SessionManager."
                )
        return self._manager.create(config, parent_id=self.id)

    def close(self) -> None:
        with self._lock:
            self.state.closed = True