from __future__ import annotations

import threading
import uuid
from datetime import datetime

from lakegen.agent import AgentConfig
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.session.environment import Environment
from lakegen.session.model import SessionInfo, SessionState
from lakegen.session.session import Session

_DEFAULT_SYSTEM_PROMPT = (
    "You are a lakehouse operator. Help users with their requests "
    "with their lakehouses"
)
_DEFAULT_MODEL = "openrouter/free"
_DEFAULT_PROVIDER = "openai"
_DEFAULT_MAX_TURNS = 10
_SESSION_PAGE_SIZE = 10


def _default_agent_config() -> AgentConfig:
    return AgentConfig(
        model=_DEFAULT_MODEL,
        system_prompt=_DEFAULT_SYSTEM_PROMPT,
        provider=_DEFAULT_PROVIDER,
        max_turns=_DEFAULT_MAX_TURNS,
    )


class SessionManager:
    """Owns session persistence and the in-process session registry."""

    def __init__(self, env: Environment | None = None) -> None:
        self.env = env if env is not None else Environment.default()
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self.env.persistence.ensure_schema()

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
                self.env.catalog_service.require(catalog_name)

            session_id = str(uuid.uuid4())

            state = SessionState(
                id=session_id,
                config=config,
                owner_id=owner_id,
                catalog_name=catalog_name,
                parent_id=parent_id,
            )
            session = Session(
                state=state,
                env=self.env,
                manager=self,
            )
            self.env.session_repository.create(
                {"id": session_id, "owner_id": owner_id}
            )
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

    def list(self, *, owner_id: str, offset: int = 0) -> list[SessionInfo]:
        """Return one persisted page, newest first."""
        if offset < 0:
            raise ValueError("offset must be non-negative.")

        with self._lock:
            rows = self.env.session_repository.list_all(
                owner_id=owner_id,
                limit=_SESSION_PAGE_SIZE,
                offset=offset,
            )
            live_ids = set(self._sessions)
            return [
                SessionInfo(
                    id=str(row["id"]),
                    name=row["name"] if isinstance(row["name"], str) else None,
                    created_at=self._created_at(row),
                    live=str(row["id"]) in live_ids,
                )
                for row in rows
            ]

    def delete(self, session_id: str) -> None:
        """Remove a session. Children are deleted with it.

        ``close()`` runs after persistence and registry updates so an in-flight
        ``send`` cannot freeze create/get/list for other sessions.
        """
        to_close, parent_id = self._collect_tree(session_id)
        self.env.session_repository.delete([session.id for session in to_close])
        self._unregister_tree(session_id, to_close, parent_id)
        for session in to_close:
            session.close()

    def _collect_tree(self, session_id: str) -> tuple[list[Session], str | None]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise BaseError(
                    ErrorCode.NOT_FOUND,
                    f"Session {session_id!r} not found.",
                )

            to_close: list[Session] = []
            stack = [session]
            while stack:
                current = stack.pop()
                to_close.append(current)
                for child_id in list(current.state.children):
                    child = self._sessions.get(child_id)
                    if child is not None:
                        stack.append(child)

            return to_close, session.state.parent_id

    def _unregister_tree(
        self,
        session_id: str,
        to_close: list[Session],
        parent_id: str | None,
    ) -> None:
        with self._lock:
            for current in to_close:
                self._sessions.pop(current.id, None)

            if parent_id is not None:
                parent = self._sessions.get(parent_id)
                if parent is not None and session_id in parent.state.children:
                    parent.state.children.remove(session_id)

    @staticmethod
    def _created_at(row: dict[str, object]) -> datetime:
        created_at = row["created_at"]
        if not isinstance(created_at, datetime):
            raise RuntimeError("Stored session created_at must be a datetime.")
        return created_at
