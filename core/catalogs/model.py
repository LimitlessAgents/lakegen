from abc import ABC
from typing import Literal, Union, Annotated
from pydantic import BaseModel, Field


class BaseIcebergCatalogSpec(BaseModel):
    """Base specification for an Iceberg catalog."""
    catalog_type: str

    access_key: str | None = None
    secret_key: str | None = None
    region: str | None  = None
    endpoint: str | None = None

    warehouse: str

    catalog_name: str = "default"


class GlueCatalogSpec(BaseIcebergCatalogSpec):
    """Catalog specification for the Glue catalog implementation."""
    catalog_type: Literal["glue"] = "glue"

    glue_additional_config: bool = False

    glue_catalog_id: str | None = None
    glue_access_key: str | None = None
    glue_secret_key: str | None = None
    glue_endpoint: str | None = None
    glue_region: str | None = None


class RestCatalogSpec(BaseIcebergCatalogSpec):
    """Catalog specification for the REST catalog implementation (e.g. Nessie, Polaris, Lakekeeper)."""
    catalog_type: Literal["rest"] = "rest"

    rest_catalog_url: str

    credential: str | None = None
    oauth2_uri: str | None = None
    rest_auth_type: str | None = None
    token: str | None = None
    scope: str | None = None

    rest_signing_name: str | None = None
    rest_signing_region: str | None = None
    rest_signing_v_4: bool = True

    no_identifier_fields: bool = False


class SqlCatalogSpec(BaseIcebergCatalogSpec):
    catalog_type: Literal["sql"] = "sql"

    database_type: Literal[
        "postgresql",
        "mysql",
        "sqlite"
    ]

    host: str
    port: int = 5432

    username: str
    password: str

    database: str


"""
Automatically loads the correct spec
based on the provided 'catalog_type'
"""
CatalogSpec = Annotated[
    GlueCatalogSpec | RestCatalogSpec | SqlCatalogSpec,
    Field(discriminator="catalog_type")
]