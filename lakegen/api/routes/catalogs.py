from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from lakegen.api.auth.authenticator import Principal
from lakegen.api.deps import get_catalogs, require_principal
from lakegen.core.catalog.model import CatalogSpec, ResolvedCatalogSpec
from lakegen.core.catalog.service import CatalogInfo, CatalogService
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode

router = APIRouter(prefix="/v1/catalogs", tags=["catalogs"])

_spec_adapter: TypeAdapter[ResolvedCatalogSpec] = TypeAdapter(CatalogSpec)


class CatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    connected: bool
    lakehouse: str | None = None
    catalog_type: str | None = None
    warehouse: str | None = None


def _to_response(info: CatalogInfo) -> CatalogResponse:
    return CatalogResponse(
        name=info.name,
        connected=info.connected,
        lakehouse=info.lakehouse,
        catalog_type=info.catalog_type,
        warehouse=info.warehouse,
    )


@router.get("")
def list_catalogs(
    _principal: Principal = Depends(require_principal),
    catalogs: CatalogService = Depends(get_catalogs),
) -> list[CatalogResponse]:
    return [_to_response(c) for c in catalogs.list()]


@router.get("/{name}")
def get_catalog(
    name: str,
    _principal: Principal = Depends(require_principal),
    catalogs: CatalogService = Depends(get_catalogs),
) -> CatalogResponse:
    return _to_response(catalogs.get(name))


@router.post("", status_code=status.HTTP_201_CREATED)
def add_catalog(
    body: dict[str, Any],
    _principal: Principal = Depends(require_principal),
    catalogs: CatalogService = Depends(get_catalogs),
) -> CatalogResponse:
    try:
        spec = _spec_adapter.validate_python(body)
    except ValidationError as exc:
        raise BaseError(
            ErrorCode.INVALID_ARGUMENT,
            "Invalid catalog specification.",
            details={"errors": exc.errors()},
        ) from exc
    return _to_response(catalogs.add(spec))


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_catalog(
    name: str,
    _principal: Principal = Depends(require_principal),
    catalogs: CatalogService = Depends(get_catalogs),
) -> Response:
    catalogs.delete(name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
