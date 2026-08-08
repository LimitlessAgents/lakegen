"""Shared argument models for Iceberg tools.

Place models here when they are reused by more than one tool module.
Tool-specific models stay in their ``*_tool.py`` file.
"""

from pydantic import BaseModel, ConfigDict, Field


class _IcebergToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CatalogConnectionArguments(_IcebergToolArguments):
    name: str = Field(description="Name of the catalog connection.")


class CatalogTableArguments(CatalogConnectionArguments):
    table: str = Field(
        description="Fully qualified table name (e.g. 'sales.orders').",
    )


class InspectTableArguments(CatalogTableArguments):
    limit: int | None = Field(
        default=None,
        ge=1,
        description="Maximum rows to return. Defaults to 100.",
    )


class TimeTravelInspectArguments(InspectTableArguments):
    snapshot_id: int | None = Field(
        default=None,
        description=(
            "Optional snapshot ID to inspect table state at a point in time."
        ),
    )
