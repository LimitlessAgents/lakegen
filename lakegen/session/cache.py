from __future__ import annotations

import threading
from collections import OrderedDict

from lakegen.session.session import Session


class SessionCache:
    """Bounded LRU cache of hydrated sessions. Pinned ids are not evicted."""

    def __init__(self, max_size: int) -> None:
        if max_size < 1:
            raise ValueError("max_size must be positive.")
        self._max_size = max_size
        self._items: OrderedDict[str, Session] = OrderedDict()
        self._pin_counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            session = self._items.get(session_id)
            if session is None:
                return None
            self._items.move_to_end(session_id)
            return session

    def set(self, session_id: str, session: Session) -> None:
        with self._lock:
            if session_id in self._items:
                self._items.move_to_end(session_id)
            self._items[session_id] = session
            self._evict()

    def pop(self, session_id: str) -> None:
        with self._lock:
            self._items.pop(session_id, None)

    def pin(self, session_id: str) -> None:
        with self._lock:
            self._pin_counts[session_id] = self._pin_counts.get(session_id, 0) + 1

    def unpin(self, session_id: str) -> None:
        with self._lock:
            count = self._pin_counts.get(session_id, 0)
            if count <= 1:
                self._pin_counts.pop(session_id, None)
            else:
                self._pin_counts[session_id] = count - 1
            self._evict()

    def _evict(self) -> None:
        while len(self._items) > self._max_size:
            evicted = False
            for session_id in self._items:
                if session_id in self._pin_counts:
                    continue
                self._items.pop(session_id)
                evicted = True
                break
            if not evicted:
                return
