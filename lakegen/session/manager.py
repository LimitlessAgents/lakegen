from __future__ import annotations

import threading
import uuid

from lakegen.agent import AgentConfig
from lakegen.core.catalog.service import catalog_service
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.session.environment import Environment
from lakegen.session.model import SessionState
from lakegen.session.session import Session

_DEFAULT_SYSTEM_PROMPT = (
    "You are a lakehouse operator. Help users with their requests "
    "with their lakehouses"
)
_DEFAULT_MODEL = "openrouter/free"
_DEFAULT_PROVIDER = "openai"
_DEFAULT_MAX_TURNS = 10


def _default_agent_config() -> AgentConfig:
    return AgentConfig(
        model=_DEFAULT_MODEL,
        system_prompt=_DEFAULT_SYSTEM_PROMPT,
        provider=_DEFAULT_PROVIDER,
        max_turns=_DEFAULT_MAX_TURNS,
    )


class SessionManager:
    """Owns live sessions for one process. No persistence yet."""

    def __init__(self, env: Environment | None = None) -> None:
        self.env = env if env is not None else Environment.default()
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(
        self,
        config: AgentConfig | None = None,
        *,
        owner_id: str,
        catalog_name: str | None = None,
        parent_id: str | None = None,
    ) -> Session:
        """Create a new session. Pass ``parent_id`` for a subagent thread.

        Omitting ``config`` uses session defaults. Root sessions may omit
        ``catalog_name``; it must be supplied on the first turn. Child sessions
        inherit the parent's active catalog.
        """
        if config is None:
            config = _default_agent_config()

        with self._lock:
            if parent_id is not None and parent_id not in self._sessions:
                raise BaseError(
                    ErrorCode.NOT_FOUND,
                    f"Parent session {parent_id!r} not found.",
                )

            if parent_id is not None:
                catalog_name = self._sessions[parent_id].state.catalog_name
            elif catalog_name is not None:
                catalog_service.require(catalog_name)

            session_id = str(uuid.uuid4())

            state = SessionState(
                id=session_id,
                config=config,
                owner_id=owner_id,
                catalog_name=catalog_name,
                parent_id=parent_id,
            )
            session = Session(state=state, env=self.env, manager=self)
            self._sessions[session_id] = session

            if parent_id is not None:
                self._sessions[parent_id].state.children.append(session_id)

            return session

    def get(self, session_id: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise BaseError(
                    ErrorCode.NOT_FOUND,
                    f"Session {session_id!r} not found.",
                )
            return session

    def list(self) -> list[Session]:
        with self._lock:
            return list(self._sessions.values())

    def delete(self, session_id: str) -> None:
        """Remove a session. Children are deleted with it.

        The manager lock is only held while updating the registry. ``close()``
        runs afterward so an in-flight ``send`` on the deleted session cannot
        freeze create/get/list for other sessions.
        """
        to_close = self._unregister_tree(session_id)
        for session in to_close:
            session.close()

    def _unregister_tree(self, session_id: str) -> list[Session]:
        """Pop a session and its descendants from the registry. Caller closes them."""
        with self._lock:
            session = self._sessions.pop(session_id, None)
            if session is None:
                raise BaseError(
                    ErrorCode.NOT_FOUND,
                    f"Session {session_id!r} not found.",
                )

            parent_id = session.state.parent_id
            if parent_id is not None:
                parent = self._sessions.get(parent_id)
                if parent is not None and session_id in parent.state.children:
                    parent.state.children.remove(session_id)

            to_close: list[Session] = []
            stack = [session]
            while stack:
                current = stack.pop()
                to_close.append(current)
                for child_id in list(current.state.children):
                    child = self._sessions.pop(child_id, None)
                    if child is not None:
                        stack.append(child)
            return to_close
