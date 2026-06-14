from typing import Any

from connection_registry.registry import conreg
from error.base import BaseError

from tool.model import ToolDefinition, ToolOutput, ToolParameters
from tool.registry import register_tool

_KIND = "catalog"


def iceberg_list_namespaces(name: str) -> ToolOutput:
    try:
        catalog = conreg.open_connection(_KIND, name)
        # print("Got catalog object:", type(catalog))
        namespaces = catalog.list_namespaces()
        return ToolOutput(ok=True, response=namespaces)
    except BaseError as e:
        return ToolOutput(
            ok=False,
            error={"code": e.code.value, "message": e.message},
        )


register_tool(
    _KIND,
    ToolDefinition(
        name="iceberg_list_namespaces",
        description="Lists all the namespaces in the Iceberg catalog",
        parameters=ToolParameters(
            type="object",
            properties={
                "name": {
                    "type": "string",
                    "description": "The name of the Iceberg catalog",
                },
            },
            required=["name"],
            additionalProperties=False,
        ),
        handler=iceberg_list_namespaces,
    ),
)
