from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from lakegen.api.auth.authenticator import Principal
from lakegen.api.deps import get_catalogs, require_principal
from lakegen.api.responses import SERVICE_ERROR_RESPONSES
from lakegen.api.schema import CatalogResponse
from lakegen.core.catalog.model import CatalogSpec
from lakegen.core.catalog.service import CatalogInfo, CatalogService

router = APIRouter(
    prefix="/v1/catalogs",
    tags=["catalogs"],
    responses=SERVICE_ERROR_RESPONSES,
)


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
    body: CatalogSpec,
    _principal: Principal = Depends(require_principal),
    catalogs: CatalogService = Depends(get_catalogs),
) -> CatalogResponse:
    return _to_response(catalogs.add(body))


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_catalog(
    name: str,
    _principal: Principal = Depends(require_principal),
    catalogs: CatalogService = Depends(get_catalogs),
) -> Response:
    catalogs.delete(name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
