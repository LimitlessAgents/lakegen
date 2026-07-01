"""Convert Pydantic tool parameter models into schemas for the agent.

Each registered tool has a params model (for example ``ListNamespacesParams``).
This module reads that model and builds a flat parameter schema the agent can
use when deciding what to pass to a tool.

The output is not full JSON Schema. It is a small, fixed shape:

- ``name``: tool name
- ``description``: what the tool does
- ``params``: one entry per model field, each with ``type``, ``description``,
  ``required``, and optionally ``default``

Field descriptions come from ``Field(description=...)`` on the Pydantic model.
Field types are mapped to simple names like ``string``, ``integer``, and
``boolean`` so the agent gets easy-to-read metadata.
"""

from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo


def _field_type_name(annotation: Any) -> str:
    """Map a Pydantic field type to a simple type name for the tool schema."""
    origin = get_origin(annotation)
    if origin is Union:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return _field_type_name(args[0])
    if annotation is str:
        return "string"
    if annotation is int:
        return "integer"
    if annotation is float:
        return "number"
    if annotation is bool:
        return "boolean"
    return "string"


def _field_meta(field_name: str, field_info: FieldInfo) -> dict[str, Any]:
    """Build the schema entry for one tool parameter field."""
    meta: dict[str, Any] = {
        "type": _field_type_name(field_info.annotation),
        "description": field_info.description or "",
        "required": field_info.is_required(),
    }
    if not field_info.is_required():
        default = field_info.default
        if default is not None:
            meta["default"] = default
    return meta


def params_model_to_tool_dict(
    name: str,
    description: str,
    params_model: type[BaseModel],
) -> dict[str, Any]:
    """Build the tool schema dict used at registration time.

    Reads ``params_model.model_fields`` and returns a dict suitable for
    ``ToolDefinition``. The agent later receives this via
    ``ToolDefinition.to_dict()``.
    """
    return {
        "name": name,
        "description": description,
        "params": {
            field_name: _field_meta(field_name, field_info)
            for field_name, field_info in params_model.model_fields.items()
        },
    }
