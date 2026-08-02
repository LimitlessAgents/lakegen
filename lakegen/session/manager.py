import threading

from lakegen.agent import AgentConfig
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.session.environment import Environment
from lakegen.session.model import SessionState
from lakegen.session.session import Session


class SessionManager:
    """Owns live sessions for one process. No persistence yet."""

    def __init__(self, env: Environment | None = None) -> None:
        self.env = env if env is not None else Environment.default()
        self._sessions: dict[int, Session] = {}
        self._lock = threading.Lock()
        self._next_id = 1

    def create(
        self,
        config: AgentConfig,
        *,
        parent_id: int | None = None,
    ) -> Session:
        """Create a new session. Pass ``parent_id`` for a subagent thread."""
        with self._lock:
            if parent_id is not None and parent_id not in self._sessions:
                raise BaseError(
                    ErrorCode.NOT_FOUND,
                    f"Parent session {parent_id!r} not found.",
                )

            session_id = self._next_id
            self._next_id += 1

            state = SessionState(
                id=session_id,
                config=config,
                parent_id=parent_id,
            )
            session = Session(state=state, env=self.env, manager=self)
            self._sessions[session_id] = session

            if parent_id is not None:
                self._sessions[parent_id].state.children.append(session_id)

            return session

    def get(self, session_id: int) -> Session:
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

    def delete(self, session_id: int) -> None:
        """Remove a session. Children are deleted with it."""
        with self._lock:
            session = self._sessions.pop(session_id, None)
            if session is None:
                raise BaseError(
                    ErrorCode.NOT_FOUND,
                    f"Session {session_id!r} not found.",
                )

            session.close()

            for child_id in list(session.state.children):
                self._delete_unlocked(child_id)

            parent_id = session.state.parent_id
            if parent_id is not None:
                parent = self._sessions.get(parent_id)
                if parent is not None and session_id in parent.state.children:
                    parent.state.children.remove(session_id)

    def _delete_unlocked(self, session_id: int) -> None:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return
        session.close()
        for child_id in list(session.state.children):
            self._delete_unlocked(child_id)
