from typing import Any

from tool.model import ToolDefinition


class Registry:
    self._all_available_tools: dict[str, dict[str, ToolDefinition]] = {}

    def register(name: str, schema: dict[str, Any], handler: Callable, requires_env: bool = False):
        self._all_available_tools[name] = ToolDefinition(
            name=name,
            description=schema["description"],
            schema=schema,
            handler=handler,
            requires_env=requires_env
        )
    
    def list_tool_names(self) -> list[ToolDefinition]:
        return self._all_available_tools.keys()

    def get_all_tools_info(self) -> dict[str, ToolDefinition]:
        return self._all_available_tools

    def get_all_tools_description(self) -> dict[str, str]:
        return {name: tooldef.description for name, tooldef in self._all_available_tools.items()}

    def get_tool_schema(self, tool_name: str) -> dict[str, Any]:
        return self._all_available_tools[tool_name].schema


