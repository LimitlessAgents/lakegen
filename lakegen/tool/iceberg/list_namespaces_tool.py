from typing import Any

from lakegen.core.connection_registry.registry import conreg
from lakegen.core.error.base import BaseError

from lakegen.tool.registry import registry

_TOOLSET = "catalog"


def iceberg_list_namespaces(params: dict[str, Any]):
    catalog = conreg.open_connection(_TOOLSET, params["name"])
    namespaces = catalog.list_namespaces()
    return namespaces

SCHEMA={
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
}

registry.register(
    toolset=_TOOLSET,
    name="iceberg_list_namespaces",
    schema=SCHEMA,
    handler=iceberg_list_namespaces,
)
