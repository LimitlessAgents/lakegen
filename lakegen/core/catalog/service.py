"""Catalog management API for the product (UI/API/CLI).

Callers should use ``CatalogService`` for persistence and live connections.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from lakegen.core.catalog.base import BaseCatalog
from lakegen.core.catalog.factory import create_catalog
from lakegen.core.catalog.model import (
    ResolvedCatalogSpec,
    resolve_catalog_spec,
)
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.core.persistence.repository.catalog_repository import (
    CatalogRepository,
    catalog_repository,
)


@dataclass(frozen=True)
class CatalogInfo:
    """Non-secret view of a registered catalog connection."""

    name: str
    connected: bool
    lakehouse: str | None = None
    catalog_type: str | None = None
    warehouse: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name,
            "connected": self.connected,
        }
        if self.lakehouse is not None:
            data["lakehouse"] = self.lakehouse
        if self.catalog_type is not None:
            data["catalog_type"] = self.catalog_type
        if self.warehouse is not None:
            data["warehouse"] = self.warehouse
        return data


class CatalogService:
    """Use cases for managing catalog connections."""

    def __init__(
        self,
        repository: CatalogRepository = catalog_repository,
        factory: Callable[[ResolvedCatalogSpec], BaseCatalog] = create_catalog,
    ) -> None:
        self._repository = repository
        self._factory = factory
        self._connections: dict[str, BaseCatalog] = {}
        self._lock = threading.RLock()

    def add(self, spec: ResolvedCatalogSpec) -> CatalogInfo:
        """Register, open, and persist a catalog. Fails if the name exists."""
        with self._lock:
            if self.exists(spec.name):
                raise BaseError(
                    ErrorCode.ALREADY_EXISTS,
                    f"Catalog {spec.name!r} is already registered.",
                )

            catalog = self._open_connection(spec)
            try:
                self._repository.create(
                    spec.model_dump(exclude_none=True),
                )
            except Exception:
                catalog.close()
                raise

            self._connections[spec.name] = catalog
            return self._info_from_spec(spec, connected=True)

    def test_connection(self, catalog: BaseCatalog) -> None:
        """Run the connection policy used before a catalog is persisted."""
        catalog.test_connection()

    def get_connection(self, name: str) -> BaseCatalog:
        """Return a cached catalog or rebuild it from its stored specification."""
        with self._lock:
            connection = self._connections.get(name)
            if connection is not None:
                return connection

            spec = resolve_catalog_spec(self._repository.get(name))
            connection = self._open_connection(spec)
            self._connections[name] = connection
            return connection

    def delete(self, name: str) -> None:
        """Delete a catalog and close its cached connection."""
        with self._lock:
            self.require(name)
            self._repository.delete(name)
            connection = self._connections.pop(name, None)
            if connection is not None:
                connection.close()

    def list(self) -> list[CatalogInfo]:
        """Return all registered catalogs with public metadata."""
        return [
            self._info_from_metadata(
                metadata,
                connected=str(metadata["name"]) in self._connections,
            )
            for metadata in self._repository.list_metadata()
        ]

    def get(self, name: str) -> CatalogInfo:
        """Return public metadata for one catalog."""
        metadata = self._repository.get_metadata(name)
        return self._info_from_metadata(
            metadata,
            connected=name in self._connections,
        )

    def exists(self, name: str) -> bool:
        return self._repository.exists(name)

    def require(self, name: str) -> None:
        """Raise if ``name`` is missing or not registered."""
        if not name:
            raise BaseError(ErrorCode.INVALID_ARGUMENT, "catalog_name is required.")
        if not self.exists(name):
            raise BaseError(
                ErrorCode.NOT_FOUND,
                f"Catalog {name!r} is not registered.",
            )

    def _open_connection(self, spec: ResolvedCatalogSpec) -> BaseCatalog:
        catalog = self._factory(spec)
        try:
            connection = catalog.connect()
            self.test_connection(connection)
            return connection
        except Exception:
            catalog.close()
            raise

    @staticmethod
    def _info_from_spec(
        spec: ResolvedCatalogSpec,
        *,
        connected: bool,
    ) -> CatalogInfo:
        return CatalogInfo(
            name=spec.name,
            connected=connected,
            lakehouse=spec.lakehouse,
            catalog_type=spec.catalog_type,
            warehouse=spec.warehouse,
        )

    @staticmethod
    def _info_from_metadata(
        metadata: Mapping[str, object],
        *,
        connected: bool,
    ) -> CatalogInfo:
        return CatalogInfo(
            name=str(metadata["name"]),
            connected=connected,
            lakehouse=CatalogService._optional_string(metadata.get("lakehouse")),
            catalog_type=CatalogService._optional_string(
                metadata.get("catalog_type")
            ),
            warehouse=CatalogService._optional_string(metadata.get("warehouse")),
        )

    @staticmethod
    def _optional_string(value: object) -> str | None:
        return value if isinstance(value, str) else None


catalog_service = CatalogService()
