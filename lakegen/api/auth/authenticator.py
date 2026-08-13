from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from starlette.requests import Request


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated caller identity."""

    id: str
    display_name: str | None = None


@runtime_checkable
class Authenticator(Protocol):
    def resolve(self, request: Request) -> Principal:
        """Resolve the caller from the HTTP request."""
        ...
