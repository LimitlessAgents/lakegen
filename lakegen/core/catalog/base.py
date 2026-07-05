"""Common catalog interface for all lakehouse backends."""

from abc import ABC, abstractmethod
from typing import Any, Self



class BaseCatalog(ABC):
    """Operations exposed to tools (list namespaces, tables, etc.).

    Note: listing/loading methods currently return backend-native objects (e.g.
    PyIceberg types), so callers should not assume a normalized shape yet.
    """

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
        """List all namespaces."""
        ...

    @abstractmethod
    def list_tables(self, namespace: str) -> list[Any]:
        """List tables in a namespace."""
        ...

    @abstractmethod
    def load_table(self, table_name: str) -> Any:
        """Load a table by name."""
        ...
