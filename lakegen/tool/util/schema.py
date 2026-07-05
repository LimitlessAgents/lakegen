"""Build tool metadata dicts from tool parameter providers.

Each tool's params provider is converted to JSON Schema via
``model_json_schema()`` and wrapped with ``name`` and ``description`` for
``ToolDefinition``.
"""

from typing import Any

from lakegen.tool.model import ToolParams


def params_model_to_tool_dict(
    name: str,
    description: str,
    params_model: ToolParams,
) -> dict[str, Any]:
    """Build the tool schema dict used at registration time.

    Calls ``params_model.model_json_schema()`` and returns a dict suitable for
    ``ToolDefinition``. The agent later receives this via
    ``ToolDefinition.to_dict()``. Works for both Pydantic ``BaseModel``
    subclasses and union adapters such as ``CatalogSpecParams``.
    """
    return {
        "name": name,
        "description": description,
        "params": params_model.model_json_schema(),
    }
