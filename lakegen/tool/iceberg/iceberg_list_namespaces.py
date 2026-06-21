from typing import Any

from lakegen.core.connection_registry.registry import conreg
from lakegen.core.error.base import BaseError

from lakegen.tool.model import ToolOutput
from lakegen.tool.registry import registry

_TOOLSET = "catalog"


def iceberg_list_namespaces(params: dict[str, Any]) -> ToolOutput:
    try:
        catalog = conreg.open_connection(_TOOLSET, params["name"])
        namespaces = catalog.list_namespaces()
        return ToolOutput(ok=True, response=namespaces)
    except BaseError as e:
        return ToolOutput(
            ok=False,
            error={"code": e.code.value, "message": e.message},
        )


registry.register(
    kind=_TOOLSET,
    name="iceberg_list_namespaces",
    schema={
        "name": "iceberg_list_namespaces",
        "description": "Lists all the namespaces in the Iceberg catalog",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the Iceberg catalog",
                },
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    handler=iceberg_list_namespaces,
)
