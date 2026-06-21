from typing import Any

from pydantic import ValidationError

from lakegen.core.catalog.base import BaseCatalog
from lakegen.core.catalog.iceberg import IcebergCatalog
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode

from lakegen.core.catalog.model import CatalogSpec, GlueCatalogSpec, RestCatalogSpec, SqlCatalogSpec
from pydantic import TypeAdapter


CATALOG_TYPE_DICT = {
    "iceberg": IcebergCatalog,
}

_catalog_spec_adapter = TypeAdapter(CatalogSpec)


def resolve_catalog_spec(spec: dict[str, Any]) -> GlueCatalogSpec | RestCatalogSpec | SqlCatalogSpec:
    temp = _catalog_spec_adapter.validate_python(spec)
    # print("TEMP:", temp)
    return temp

def resolve_catalog_type(spec: dict[str, Any]) -> type[BaseCatalog]:
    try:
        return CATALOG_TYPE_DICT[spec["catalog_kind"]]
    except KeyError:
        raise BaseError(
            ErrorCode.INVALID_ARGUMENT,
            f"Catalog kind '{catalog_kind}' doesn't exist. "
            f"Available kinds: {', '.join(CATALOG_TYPE_DICT.keys())}",
        )

def get_catalog_instance(spec: dict[str, Any]) -> BaseCatalog:
    try:
        resolved_spec = resolve_catalog_spec(spec)
    except ValidationError as e:
        raise BaseError(
            ErrorCode.INVALID_ARGUMENT,
            "Invalid catalog spec",
            details={"errors": e.errors()},
        ) from e

    # print("SPEC:", resolved_spec)

    return resolve_catalog_type(spec)(resolved_spec)
