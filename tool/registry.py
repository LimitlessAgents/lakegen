from typing import Any

from tool.model import ToolDefinition, ToolOutput

_all_available_tools: dict[str, dict[str, ToolDefinition]] = {}


def register_tool(kind: str, tool: ToolDefinition) -> None:
    """Register a tool."""
    _all_available_tools.setdefault(kind, {})[tool.name] = tool


def list_tools(kind: str | None = None) -> list[ToolDefinition]:
    if kind is not None:
        return list(_all_available_tools.get(kind, {}).values())
    return [
        tool
        for tools in _all_available_tools.values()
        for tool in tools.values()
    ]


def use_tool(kind: str, name: str, params: dict[str, Any]) -> ToolOutput:
    # print("Available tools:", _all_available_tools)
    tool = _all_available_tools.get(kind, {}).get(name)
    if tool is None:
        return ToolOutput(
            ok=False,
            error={
                "code": "TOOL_NOT_FOUND",
                "message": f"Unknown tool {name!r} in {kind!r}",
            },
        )
    return tool.handler(params)
