"""Shared argument models for Iceberg tools.

Place models here when they are reused by more than one tool module.
Tool-specific models stay in their ``*_tool.py`` file.

``name`` (catalog) is injected by ``ToolRuntime`` from the session and is
hidden from the agent-facing JSON schema.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _IcebergToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @classmethod
    def model_json_schema(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
        schema = super().model_json_schema(*args, **kwargs)
        props = schema.get("properties")
        if props is not None:
            props.pop("name", None)
        required = schema.get("required")
        if required and "name" in required:
            schema["required"] = [field for field in required if field != "name"]
        return schema


class CatalogConnectionArguments(_IcebergToolArguments):
    name: str = Field(description="Injected from the session's active catalog.")


class CatalogTableArguments(CatalogConnectionArguments):
    table: str = Field(
        description="Fully qualified table name (e.g. 'sales.orders').",
    )


class CatalogNamespaceArguments(CatalogConnectionArguments):
    namespace: str = Field(description="Namespace to list tables from.")


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
