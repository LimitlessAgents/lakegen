from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime

from lakegen.agent import AgentConfig
from lakegen.agent.serialization import conversation_from_turn_rows
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.session.cache import SessionCache
from lakegen.session.environment import Environment
from lakegen.session.model import AgentTurnInfo, SessionInfo, SessionState
from lakegen.session.session import Session
from lakegen.prompt import PROMPT as _DEFAULT_SYSTEM_PROMPT


_DEFAULT_MODEL = "openrouter/free"
_DEFAULT_PROVIDER = "openai"
_DEFAULT_MAX_TURNS = 10
_SESSION_PAGE_SIZE = 10
_DEFAULT_CACHE_SIZE = 32
_DEFAULT_HYDRATE_TURN_LIMIT = 20


def _default_agent_config() -> AgentConfig:
    return AgentConfig(
        model=_DEFAULT_MODEL,
        system_prompt=_DEFAULT_SYSTEM_PROMPT,
        provider=_DEFAULT_PROVIDER,
        max_turns=_DEFAULT_MAX_TURNS,
    )


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


class SessionManager:
    """Owns session persistence and a bounded in-process session cache."""

    def __init__(
        self,
        env: Environment | None = None,
        *,
        cache_size: int | None = None,
        hydrate_turn_limit: int | None = None,
    ) -> None:
        self.env = env if env is not None else Environment.default()
        self._cache = SessionCache(
            cache_size if cache_size is not None else _int_env(
                "LAKEGEN_SESSION_CACHE_SIZE",
                _DEFAULT_CACHE_SIZE,
            )
        )
        self._hydrate_turn_limit = (
            hydrate_turn_limit
            if hydrate_turn_limit is not None
            else _int_env(
                "LAKEGEN_SESSION_HYDRATE_TURN_LIMIT",
                _DEFAULT_HYDRATE_TURN_LIMIT,
            )
        )
        self._deleting: set[str] = set()
        self._lock = threading.Lock()
        if self.env.persistence.configured:
            self.env.persistence.ensure_schema()

    def pin_session(self, session_id: str) -> None:
        self._cache.pin(session_id)

    def unpin_session(self, session_id: str) -> None:
        self._cache.unpin(session_id)

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
            if parent_id is not None and parent_id in self._deleting:
                raise BaseError(
                    ErrorCode.NOT_FOUND,
                    f"Parent session {parent_id!r} not found.",
                )

            if parent_id is not None:
                catalog_name = self._catalog_name_for_parent(parent_id)
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
                {
                    "id": session_id,
                    "owner_id": owner_id,
                    "catalog_name": catalog_name,
                }
            )
            self._cache.set(session_id, session)

            if parent_id is not None:
                parent = self._cache.get(parent_id)
                if parent is not None:
                    parent.state.children.append(session_id)

            return session

    def get(self, session_id: str) -> Session:
        with self._lock:
            if session_id in self._deleting:
                raise BaseError(
                    ErrorCode.NOT_FOUND,
                    f"Session {session_id!r} not found.",
                )
            cached = self._cache.get(session_id)
            if cached is not None:
                return cached

        session = self._hydrate(session_id)

        with self._lock:
            if session_id in self._deleting:
                raise BaseError(
                    ErrorCode.NOT_FOUND,
                    f"Session {session_id!r} not found.",
                )
            self._cache.set(session_id, session)
            return session

    def list(self, *, owner_id: str, offset: int = 0) -> list[SessionInfo]:
        """Return one persisted page, newest first."""
        if offset < 0:
            raise ValueError("offset must be non-negative.")

        rows = self.env.session_repository.list(
            owner_id,
            offset,
            _SESSION_PAGE_SIZE,
        )
        return [
            SessionInfo(
                id=str(row["id"]),
                name=row["name"] if isinstance(row["name"], str) else None,
                created_at=self._created_at(row),
                catalog_name=self._optional_catalog_name(row),
            )
            for row in rows
        ]

    def list_turns(
        self,
        session_id: str,
        *,
        owner_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> list[AgentTurnInfo]:
        if offset < 0:
            raise ValueError("offset must be non-negative.")
        if limit <= 0:
            raise ValueError("limit must be positive.")
        row = self.env.session_repository.get(session_id)
        if row.get("owner_id") != owner_id:
            raise BaseError(
                ErrorCode.NOT_FOUND,
                f"Session {session_id!r} not found.",
            )
        rows = self.env.agent_turn_repository.list(session_id, offset, limit)
        return [self._agent_turn_info(row) for row in rows]

    def delete(self, session_id: str) -> None:
        """Remove a persisted session and drop any cached copy."""
        with self._lock:
            if session_id in self._deleting:
                raise BaseError(
                    ErrorCode.NOT_FOUND,
                    f"Session {session_id!r} not found.",
                )
            cached = self._cache.get(session_id)

        closed: Session | None = None
        if cached is not None:
            with cached._lock:
                self._mark_deleting(session_id)
                cached.state.closed = True
                closed = cached
            self._cache.pop(session_id)
        else:
            self._mark_deleting(session_id)

        try:
            self.env.session_repository.delete(session_id)
        except Exception:
            if closed is not None:
                closed._reopen()
                self._cache.set(session_id, closed)
            with self._lock:
                self._deleting.discard(session_id)
            raise

        with self._lock:
            self._deleting.discard(session_id)

    def _mark_deleting(self, session_id: str) -> None:
        with self._lock:
            if session_id in self._deleting:
                raise BaseError(
                    ErrorCode.NOT_FOUND,
                    f"Session {session_id!r} not found.",
                )
            self._deleting.add(session_id)

    def _hydrate(self, session_id: str) -> Session:
        row = self.env.session_repository.get(session_id)
        turn_rows = self.env.agent_turn_repository.list(
            session_id,
            0,
            self._hydrate_turn_limit,
        )
        messages = conversation_from_turn_rows(turn_rows)
        state = SessionState(
            id=session_id,
            config=_default_agent_config(),
            owner_id=str(row["owner_id"]),
            catalog_name=self._optional_catalog_name(row),
            created_at=self._created_at(row),
            messages=messages,
        )
        return Session(state=state, env=self.env, manager=self)

    def _catalog_name_for_parent(self, parent_id: str) -> str | None:
        parent = self._cache.get(parent_id)
        if parent is not None:
            return parent.state.catalog_name
        row = self.env.session_repository.get(parent_id)
        return self._optional_catalog_name(row)

    @staticmethod
    def _optional_catalog_name(row: dict[str, object]) -> str | None:
        catalog_name = row.get("catalog_name")
        return catalog_name if isinstance(catalog_name, str) else None

    @staticmethod
    def _created_at(row: dict[str, object]) -> datetime:
        created_at = row["created_at"]
        if not isinstance(created_at, datetime):
            raise RuntimeError("Stored session created_at must be a datetime.")
        return created_at

    @staticmethod
    def _agent_turn_info(row: dict[str, object]) -> AgentTurnInfo:
        result = row["result"]
        if not isinstance(result, dict):
            raise RuntimeError("Stored agent turn result must be an object.")
        return AgentTurnInfo(
            id=str(row["id"]),
            created_at=SessionManager._created_at(row),
            result=result,
        )
