"""Common catalog interface for all lakehouse backends.

All methods that return catalog data must return JSON-native types only
(strings, dicts, lists of strings/dicts). Implementations must not return
backend-specific objects; the conversion is the implementation's responsibility.
"""

from abc import ABC, abstractmethod
from typing import Any, Self


class BaseCatalog(ABC):
    """Operations exposed to tools (list namespaces, tables, etc.)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Connection name."""
        ...

    @abstractmethod
    def connect(self) -> Self:
        """Open the catalog connection."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Close the connection if open."""
        ...

    @abstractmethod
    def list_namespaces(self) -> list[str]:
        """Return all namespace names as dotted strings (e.g. ``"sales.q1"``)."""
        ...

    @abstractmethod
    def list_tables(self, namespace: str) -> list[str]:
        """Return table names in a namespace as dotted strings."""
        ...

    @abstractmethod
    def load_table(self, table_name: str) -> dict[str, Any]:
        """Return table metadata as a plain dict (name, location, schema)."""
        ...
