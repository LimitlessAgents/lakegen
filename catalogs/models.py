from abc import ABC
from typing import Literal, Optional, Union, Annotated
from pydantic import BaseModel, Field


class BaseIcebergCatalogSpec(BaseModel):
    """Base specification for an Iceberg catalog."""
    catalog_type: str

    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    s3_region: str

    warehouse: str

    catalog_name: Optional[str] = "default"


class GlueCatalogSpec(BaseIcebergCatalogSpec):
    """Catalog specification for the Glue catalog implementation."""
    catalog_type: Literal["glue"]

    s3_endpoint: Optional[str] = None

    glue_additional_config: bool = False

    glue_catalog_id: Optional[str] = None
    glue_access_key: Optional[str] = None
    glue_secret_key: Optional[str] = None
    glue_endpoint: Optional[str] = None
    glue_region: Optional[str] = None


class RestCatalogSpec(BaseIcebergCatalogSpec):
    """Catalog specification for the REST catalog implementation (e.g. Nessie, Polaris, Lakekeeper)."""
    catalog_type: Literal["rest"] = "rest"

    rest_catalog_url: str

    credential: Optional[str] = None
    oauth2_uri: Optional[str] = None
    rest_auth_type: Optional[str] = None
    token: Optional[str] = None
    scope: Optional[str] = None

    rest_signing_name: Optional[str] = None
    rest_signing_region: Optional[str] = None
    rest_signing_v_4: bool = True

    no_identifier_fields: bool = False

    s3_endpoint: Optional[str] = None


"""
Automatically loads the correct spec
based on the provided 'catalog_type'
"""
CatalogSpec = Annotated[
    GlueCatalogSpec | RestCatalogSpec,
    Field(discriminator="catalog_type")
]