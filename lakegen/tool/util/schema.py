"""Build tool metadata dicts from tool argument providers.

Each tool's arguments provider is converted to JSON Schema via
``model_json_schema()`` and wrapped with ``name`` and ``description`` for
``ToolDefinition``.
"""

from typing import Any

from lakegen.tool.model import ToolArguments


def arguments_model_to_tool_dict(
    name: str,
    description: str,
    arguments_model: ToolArguments,
) -> dict[str, Any]:
    """Build the tool schema dict used at registration time.

    Calls ``arguments_model.model_json_schema()`` and returns a dict suitable for
    ``ToolDefinition``. The agent later receives this via
    ``ToolDefinition.to_dict()``. Works for both Pydantic ``BaseModel``
    subclasses and union adapters such as ``CatalogSpecArguments``.
    """
    return {
        "name": name,
        "description": description,
        "arguments": arguments_model.model_json_schema(),
    }
