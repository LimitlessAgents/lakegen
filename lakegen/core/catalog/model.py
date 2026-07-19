"""Catalog connection specs.

Each spec is a validated config for one catalog backend (glue, rest, or sql).
Specs stay as objects in memory; they are serialized to JSON only when saved.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


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

    def iceberg_kwargs(self) -> tuple[str, dict[str, Any]]:
        """Build the (name, properties) pair PyIceberg's ``load_catalog`` expects.

        Dumped ``by_alias`` so field names become PyIceberg's dotted property
        keys (e.g. ``access_key`` -> ``s3.access-key-id``). The connection
        identity fields are excluded since they are not catalog properties.
        """
        props = self.model_dump(
            by_alias=True,
            exclude_none=True,
            exclude_unset=True,
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
    # The base S3 keys apply when storage and Glue live in the same account;
    # these glue_* keys cover the cross-account case where the catalog account
    # differs from the storage account. Both map to the same s3.* properties.
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
        description="AWS SigV4 service name.",
    )
    rest_signing_region: str | None = Field(
        default=None,
        description="AWS SigV4 region.",
    )
    rest_signing_v_4: bool = Field(
        default=True,
        description="Use AWS SigV4 signing.",
    )
    no_identifier_fields: bool = Field(
        default=False,
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
        """Assemble the DB connection URI from the individual fields above."""
        return (
            f"{self.database_type}://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    def iceberg_kwargs(self) -> tuple[str, dict[str, Any]]:
        # PyIceberg's SQL catalog takes a single ``uri``, so the individual DB
        # component fields are excluded and collapsed into it here.
        props = self.model_dump(
            by_alias=True,
            exclude_none=True,
            exclude_unset=True,
            exclude={"lakehouse", "catalog_type", "name",
                    "database_type", "username", "password", "host", "port", "database"},
        )
        props["uri"] = self.uri()
        return self.name, props


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


class CatalogSpecArguments:
    """Tool arguments provider for the catalog discriminated union.

    Presents the ``model_validate`` / ``model_json_schema`` surface the tool
    registry and runtime expect, but delegates to the union ``TypeAdapter`` so
    validation dispatches on ``catalog_type`` and the advertised schema covers
    every backend variant.
    """

    @staticmethod
    def model_validate(value: Any) -> ResolvedCatalogSpec:
        return _catalog_spec_adapter.validate_python(value)

    @staticmethod
    def model_json_schema() -> dict[str, Any]:
        return _catalog_spec_adapter.json_schema()
