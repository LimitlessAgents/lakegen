"""Create catalog connections from validated specs."""

from lakegen.core.catalog.base import BaseCatalog
from lakegen.core.catalog.iceberg import IcebergCatalog
from lakegen.core.catalog.model import ResolvedCatalogSpec
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode

# Maps lakehouse name to its catalog implementation.
CATALOG_TYPE_DICT: dict[str, type[BaseCatalog]] = {
    "iceberg": IcebergCatalog,
}


def resolve_catalog_type(lakehouse: str) -> type[BaseCatalog]:
    """Return the catalog class for a lakehouse type."""
    if not lakehouse or lakehouse not in CATALOG_TYPE_DICT:
        raise BaseError(
            ErrorCode.INVALID_ARGUMENT,
            f"Invalid catalog kind {lakehouse!r}. "
            f"Available kinds: {list(CATALOG_TYPE_DICT)}",
        )
    return CATALOG_TYPE_DICT[lakehouse]


def get_catalog_instance(spec: ResolvedCatalogSpec) -> BaseCatalog:
    """Build a catalog client from a validated spec."""
    return resolve_catalog_type(spec.lakehouse)(spec)
