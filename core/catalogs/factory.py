"""Factory for building catalog implementations from raw spec dicts.

This is the single seam between a stored connection's credentials and a concrete
``BaseCatalog``. Validation routes the dict to the matching spec via the
``catalog_type`` discriminator; today every supported type is Iceberg-backed,
but new engines can branch here without touching the connection manager.
"""

from typing import Any
from pydantic import TypeAdapter

from catalogs import BaseCatalog, IcebergCatalog, CatalogSpec

# Reused adapter so the discriminated union is compiled once, not per call.
_CATALOG_SPEC_ADAPTER: TypeAdapter = TypeAdapter(CatalogSpec)



def build_catalog(spec_dict: dict[str, Any]) -> BaseCatalog:
    """Validate a raw spec dict and construct the matching catalog.

    Args:
        spec_dict: Connection fields (e.g. from the credential store), including
            a ``catalog_type`` used to select the concrete spec.

    Returns:
        An opened ``BaseCatalog`` implementation.
    """
    spec = _CATALOG_SPEC_ADAPTER.validate_python(spec_dict)
    # Glue / REST / SQL are all Iceberg-backed catalogs today.
    return IcebergCatalog(spec.model_dump())
