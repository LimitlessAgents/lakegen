from typing import Any

from lakegen.core.catalog.base import BaseCatalog
from lakegen.core.catalog.model import (
    CatalogSpec,
    CatalogSpecArguments,
    GlueCatalogSpec,
    ResolvedCatalogSpec,
    RestCatalogSpec,
    SqlCatalogSpec,
    resolve_catalog_spec,
)

# Keep service imports lazy so catalog implementations can import model types
# without initializing the process-wide catalog service.

__all__ = [
    "BaseCatalog",
    "CatalogInfo",
    "CatalogService",
    "CatalogSpec",
    "CatalogSpecArguments",
    "GlueCatalogSpec",
    "ResolvedCatalogSpec",
    "RestCatalogSpec",
    "SqlCatalogSpec",
    "catalog_service",
    "resolve_catalog_spec",
]


def __getattr__(name: str) -> Any:
    if name in {"CatalogInfo", "CatalogService", "catalog_service"}:
        from lakegen.core.catalog import service as _service

        return getattr(_service, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
