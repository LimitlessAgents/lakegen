from typing import Any

from connection_registry.registry import conreg
from credential.store import store_credentials
from error.base import BaseError

from tool.model import ToolDefinition, ToolOutput
from tool.registry import register_tool

_KIND = "catalog"


def add_catalog(params: dict[str, Any]) -> ToolOutput:
    try:
        conreg.open_new_connection(_KIND, params)
        return ToolOutput(
            ok=True,
            response=f"Catalog {params['name']} successfully added.",
        )
    except BaseError as e:
        return ToolOutput(
            ok=False,
            response=f"Failed to add catalog: {params.get('name')}",
            error=e.to_dict(),
        )


tool_definition = ToolDefinition(
    name="add_catalog",
    description=(
        "Add and connect a catalog. Will interact directly with the user for "
        "getting credentials for security reasons. Use when need to add any lakehouse catalog"
    ),
    handler=add_catalog,
)


register_tool(_KIND, tool_definition)
