"""Catalog management API for the product (UI/API/CLI).

Callers should use ``CatalogService`` for add/list/delete/get — not the
credential store or connection registry directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lakegen.core.catalog.model import ResolvedCatalogSpec
from lakegen.core.connection.registry import ConnectionRegistry, conreg
from lakegen.core.credential.store import (
    delete_credentials,
    get_connection_metadata,
    list_connections,
)
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode

_KIND = "catalog"


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

    def __init__(self, registry: ConnectionRegistry | None = None) -> None:
        self._registry = registry if registry is not None else conreg

    def add(self, spec: ResolvedCatalogSpec) -> CatalogInfo:
        """Register, open, and persist a catalog. Fails if the name exists."""
        if self.exists(spec.name):
            raise BaseError(
                ErrorCode.ALREADY_EXISTS,
                f"Catalog {spec.name!r} is already registered.",
            )
        self._registry.open_new_connection(_KIND, spec)
        return self.get(spec.name)

    def delete(self, name: str) -> None:
        """Close an open connection (if any) and remove stored credentials."""
        self.require(name)
        self._registry.close_connection(_KIND, name)
        delete_credentials(_KIND, name)

    def list(self) -> list[CatalogInfo]:
        """Return all registered catalogs with public metadata."""
        return [self.get(name) for name in list_connections(_KIND)]

    def get(self, name: str) -> CatalogInfo:
        """Return public metadata for one catalog."""
        self.require(name)
        meta = get_connection_metadata(_KIND, name)
        return CatalogInfo(
            name=name,
            connected=name in self._registry.list_open(_KIND),
            lakehouse=meta.get("lakehouse"),
            catalog_type=meta.get("catalog_type"),
            warehouse=meta.get("warehouse"),
        )

    def exists(self, name: str) -> bool:
        if not name:
            return False
        return name in list_connections(_KIND)

    def require(self, name: str) -> None:
        """Raise if ``name`` is missing or not registered."""
        if not name:
            raise BaseError(ErrorCode.INVALID_ARGUMENT, "catalog_name is required.")
        if not self.exists(name):
            raise BaseError(
                ErrorCode.NOT_FOUND,
                f"Catalog {name!r} is not registered.",
            )


catalog_service = CatalogService()
