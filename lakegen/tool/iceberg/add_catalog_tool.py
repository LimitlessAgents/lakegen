from typing import Any

from lakegen.core.connection_registry.registry import conreg
from lakegen.core.error.base import BaseError

from lakegen.tool.model import ToolDefinition, ToolOutput
from lakegen.tool.registry import registry

_TOOLSET = "catalog"

def add_catalog(params: dict[str, Any]) -> None:
    conreg.open_new_connection(_TOOLSET, params)

# OPENAI TOOL FORMAT
SCHEMA = {
    "name": "add_catalog",
    "description": (
        "Add and connect a catalog. Will interact directly with the user for "
        "getting credentials for security reasons. Use when need to add any lakehouse catalog"
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": ["param_name"],
    },
}


# Register the tool. Will register by a side affect call when the module is imported
registry.register(
    toolset=_TOOLSET,
    name="add_catalog",
    schema=SCHEMA,
    handler=add_catalog,
    requires_env=True,
)