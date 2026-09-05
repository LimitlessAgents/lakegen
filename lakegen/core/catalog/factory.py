from collections.abc import Callable

from lakegen.core.catalog.base import BaseCatalog
from lakegen.core.catalog.iceberg import IcebergCatalog
from lakegen.core.catalog.model import ResolvedCatalogSpec
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode

_CATALOG_TYPES: dict[str, Callable[[ResolvedCatalogSpec], BaseCatalog]] = {
    "iceberg": IcebergCatalog,
}


def create_catalog(spec: ResolvedCatalogSpec) -> BaseCatalog:
    """Create the catalog implementation selected by the spec."""
    factory = _CATALOG_TYPES.get(spec.lakehouse)
    if factory is None:
        raise BaseError(
            ErrorCode.INVALID_ARGUMENT,
            f"Invalid catalog kind {spec.lakehouse!r}. "
            f"Available kinds: {list(_CATALOG_TYPES)}",
        )
    return factory(spec)
