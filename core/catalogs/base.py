"""Catalog interface used by lakehouse catalog implementations.

Concrete catalogs hide backend-specific details such as Iceberg REST, Glue
or JDBC behind a small common API.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseCatalog(ABC):
    """Abstract contract for catalog operations exposed to tools."""

    @abstractmethod
    def list_namespaces(self) -> list[Any]:
        """Return all namespaces available in the catalog."""
        ...

    @abstractmethod
    def list_tables(self, namespace: str) -> list[Any]:
        """Return tables available under a namespace."""
        ...

    @abstractmethod
    def load_table(self, table_name: str) -> Any:
        """Load a table by identifier from the catalog."""
        ...