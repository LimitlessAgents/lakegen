"""Catalog connection specs.

Each spec is a validated config for one catalog backend (glue, rest, or sql).
Specs stay as objects in memory; they are serialized to JSON only when saved.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, computed_field


class BaseCatalogSpec(BaseModel):
    """Shared fields for every Iceberg catalog connection."""

    model_config = ConfigDict(populate_by_name=True)

    lakehouse: Literal["iceberg"] = Field(
        description="Lakehouse type. Use 'iceberg'.",
    )
    catalog_type: str = Field(
        serialization_alias="type",
        description="Catalog backend: glue, rest, or sql.",
    )
    name: str = Field(description="Unique name for this connection.")

    access_key: str | None = Field(
        default=None,
        serialization_alias="s3.access-key-id",
        description="S3 access key ID.",
    )
    secret_key: str | None = Field(
        default=None,
        serialization_alias="s3.secret-access-key",
        description="S3 secret access key.",
    )
    region: str | None = Field(
        default=None,
        serialization_alias="s3.region",
        description="S3 region.",
    )
    endpoint: str | None = Field(
        default=None,
        serialization_alias="s3.endpoint",
        description="S3 endpoint URL.",
    )

    warehouse: str = Field(description="S3 warehouse path or bucket.")

    def pyiceberg_kwargs(self) -> tuple[str, dict[str, Any]]:
        """Build the name and properties dict expected by PyIceberg."""
        props = self.model_dump(
            by_alias=True,
            exclude_none=True,
            exclude={"lakehouse", "catalog_type", "name"},
        )
        return self.name, props


class GlueCatalogSpec(BaseCatalogSpec):
    """Catalog specification for the Glue catalog implementation."""

    catalog_type: Literal["glue"] = Field(
        default="glue",
        serialization_alias="type",
        description="Catalog backend. Use 'glue'.",
    )

    glue_additional_config: bool = Field(
        default=False,
        exclude=True,
        description="Enable extra Glue settings.",
    )

    glue_catalog_id: str | None = Field(
        default=None,
        serialization_alias="glue.id",
        description="AWS Glue catalog ID.",
    )
    glue_access_key: str | None = Field(
        default=None,
        serialization_alias="s3.access-key-id",
        description="S3 access key for Glue.",
    )
    glue_secret_key: str | None = Field(
        default=None,
        serialization_alias="s3.secret-access-key",
        description="S3 secret key for Glue.",
    )
    glue_endpoint: str | None = Field(
        default=None,
        serialization_alias="s3.endpoint",
        description="S3 endpoint for Glue.",
    )
    glue_region: str | None = Field(
        default=None,
        serialization_alias="s3.region",
        description="S3 region for Glue.",
    )


class RestCatalogSpec(BaseCatalogSpec):
    """Catalog specification for the REST catalog implementation."""

    catalog_type: Literal["rest"] = Field(
        default="rest",
        serialization_alias="type",
        description="Catalog backend. Use 'rest'.",
    )

    rest_catalog_url: str = Field(
        serialization_alias="uri",
        description="REST catalog URI.",
    )

    credential: str | None = Field(
        default=None,
        description="Auth credential.",
    )
    oauth2_uri: str | None = Field(
        default=None,
        serialization_alias="oauth2-server-uri",
        description="OAuth2 server URI.",
    )
    rest_auth_type: str | None = Field(
        default=None,
        exclude=True,
        description="REST auth type.",
    )
    token: str | None = Field(
        default=None,
        description="Bearer token.",
    )
    scope: str | None = Field(
        default=None,
        description="OAuth2 scope.",
    )

    rest_signing_name: str | None = Field(
        default=None,
        exclude=True,
        description="AWS SigV4 service name.",
    )
    rest_signing_region: str | None = Field(
        default=None,
        exclude=True,
        description="AWS SigV4 region.",
    )
    rest_signing_v_4: bool = Field(
        default=True,
        exclude=True,
        description="Use AWS SigV4 signing.",
    )
    no_identifier_fields: bool = Field(
        default=False,
        exclude=True,
        description="Omit identifier fields in REST requests.",
    )


class SqlCatalogSpec(BaseCatalogSpec):
    """Catalog specification for the SQL catalog implementation."""

    catalog_type: Literal["sql"] = Field(
        default="sql",
        serialization_alias="type",
        description="Catalog backend. Use 'sql'.",
    )

    database_type: Literal["postgresql", "mysql", "sqlite"] = Field(
        description="Database type.",
    )
    host: str = Field(description="Database host.")
    port: int = Field(default=5432, description="Database port.")
    username: str = Field(description="Database username.")
    password: str = Field(description="Database password.")
    database: str = Field(description="Database name.")

    def uri(self) -> str:
        """JDBC URI built from the connection fields above."""
        return (
            f"{self.database_type}://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    def pyiceberg_kwargs(self) -> tuple[str, dict[str, Any]]:
        name, props = super().pyiceberg_kwargs()
        for field in ("database_type", "host", "port", "username", "password", "database"):
            props.pop(field, None)
        props["uri"] = self.uri()
        return name, props


# Discriminated union of all catalog backends.
CatalogSpec = Annotated[
    GlueCatalogSpec | RestCatalogSpec | SqlCatalogSpec,
    Field(discriminator="catalog_type"),
]

ResolvedCatalogSpec = GlueCatalogSpec | RestCatalogSpec | SqlCatalogSpec

_catalog_spec_adapter = TypeAdapter(CatalogSpec)


def resolve_catalog_spec(data: dict[str, Any]) -> ResolvedCatalogSpec:
    """Parse a stored dict into a validated catalog spec."""
    return _catalog_spec_adapter.validate_python(data)


class CatalogConnectionSpec(BaseModel):
    """Tool params model. Validates input and returns a ResolvedCatalogSpec."""

    @classmethod
    def model_validate(cls, value, /, **kwargs) -> ResolvedCatalogSpec:
        return resolve_catalog_spec(value)
