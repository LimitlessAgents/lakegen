from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, computed_field


class BaseIcebergCatalogSpec(BaseModel):
    """Base specification for an Iceberg catalog."""

    model_config = ConfigDict(populate_by_name=True)

    catalog_type: str = Field(serialization_alias="type")
    name: str

    access_key: str | None = Field(default=None, serialization_alias="s3.access-key-id")
    secret_key: str | None = Field(default=None, serialization_alias="s3.secret-access-key")
    region: str | None = Field(default=None, serialization_alias="s3.region")
    endpoint: str | None = Field(default=None, serialization_alias="s3.endpoint")

    warehouse: str

    def pyiceberg_kwargs(self) -> tuple[str, dict[str, Any]]:
        props = self.model_dump(
            by_alias=True,
            exclude_none=True,
            exclude={"name"},
        )
        return self.name, props


class GlueCatalogSpec(BaseIcebergCatalogSpec):
    """Catalog specification for the Glue catalog implementation."""

    catalog_type: Literal["glue"] = Field(default="glue", serialization_alias="type")

    glue_additional_config: bool = Field(default=False, exclude=True)

    glue_catalog_id: str | None = Field(default=None, serialization_alias="glue.id")
    glue_access_key: str | None = Field(default=None, serialization_alias="s3.access-key-id")
    glue_secret_key: str | None = Field(default=None, serialization_alias="s3.secret-access-key")
    glue_endpoint: str | None = Field(default=None, serialization_alias="s3.endpoint")
    glue_region: str | None = Field(default=None, serialization_alias="s3.region")


class RestCatalogSpec(BaseIcebergCatalogSpec):
    """Catalog specification for the REST catalog implementation."""

    catalog_type: Literal["rest"] = Field(default="rest", serialization_alias="type")

    rest_catalog_url: str = Field(serialization_alias="uri")

    credential: str | None = None
    oauth2_uri: str | None = Field(default=None, serialization_alias="oauth2-server-uri")
    rest_auth_type: str | None = Field(default=None, exclude=True)
    token: str | None = None
    scope: str | None = None

    rest_signing_name: str | None = Field(default=None, exclude=True)
    rest_signing_region: str | None = Field(default=None, exclude=True)
    rest_signing_v_4: bool = Field(default=True, exclude=True)
    no_identifier_fields: bool = Field(default=False, exclude=True)


class SqlCatalogSpec(BaseIcebergCatalogSpec):
    catalog_type: Literal["sql"] = Field(default="sql", serialization_alias="type")

    database_type: Literal["postgresql", "mysql", "sqlite"] = Field(exclude=True)
    host: str = Field(exclude=True)
    port: int = Field(default=5432, exclude=True)
    username: str = Field(exclude=True)
    password: str = Field(exclude=True)
    database: str = Field(exclude=True)

    @computed_field(alias="uri")
    @property
    def uri(self) -> str:
        return (
            f"{self.database_type}://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


CatalogSpec = Annotated[
    GlueCatalogSpec | RestCatalogSpec | SqlCatalogSpec,
    Field(discriminator="catalog_type"),
]