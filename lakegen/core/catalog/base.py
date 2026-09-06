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
    def test_connection(self) -> None:
        """Verify the remote catalog is reachable with the configured credentials."""
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
    def get_table_metadata(self, table_name: str) -> dict[str, Any]:
        """Return table metadata as a plain dict (name, location, schema)."""
        ...

    @abstractmethod
    def inspect_snapshots(self, table_name: str) -> list[dict[str, Any]]:
        """Return snapshot history rows for a table."""
        ...

    @abstractmethod
    def inspect_partitions(
        self,
        table_name: str,
        *,
        snapshot_id: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Return partition summary rows for a table."""
        ...

    @abstractmethod
    def inspect_history(
        self,
        table_name: str,
        *,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Return snapshot ancestry history rows for a table."""
        ...

    @abstractmethod
    def inspect_refs(
        self,
        table_name: str,
        *,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Return branch and tag references for a table."""
        ...

    @abstractmethod
    def inspect_files(
        self,
        table_name: str,
        *,
        snapshot_id: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Return data file rows for a table snapshot."""
        ...

    @abstractmethod
    def inspect_entries(
        self,
        table_name: str,
        *,
        snapshot_id: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Return manifest entry rows for a table snapshot."""
        ...

    @abstractmethod
    def inspect_manifests(
        self,
        table_name: str,
        *,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Return manifest file rows for a table."""
        ...

    @abstractmethod
    def inspect_metadata_log(
        self,
        table_name: str,
        *,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Return metadata log entry rows for a table."""
        ...
