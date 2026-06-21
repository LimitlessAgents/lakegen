from typing import Any, Callable

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.tool.model import ToolDefinition


class ToolRegistry:
    def __init__(self):
        self.__all_available_tools: dict[str, dict[str, ToolDefinition]] = {}

    def register(
        self,
        toolset: str,
        name: str,
        schema: dict[str, Any],
        handler: Callable,
        requires_env: bool = False,
        description: str = ""
        ):
        self.__all_available_tools.setdefault(toolset, {})[name] = ToolDefinition(
            name=name,
            description=description or schema.get("description", ""),
            schema=schema,
            handler=handler,
            requires_env=requires_env
        )

    def list_tool_names(self) -> list[str]:
        try:
            return [
                name
                for tools in self.__all_available_tools.values()
                for name in tools
            ]
        except BaseError:
            raise
        except Exception as e:
            raise BaseError(
                ErrorCode.INTERNAL,
                "Failed to list tool names.",
                cause=e,
            ) from e

    def get_all_tools_info(self) -> dict[str, dict[str, ToolDefinition]]:
        try:
            return {
                toolset: dict(tools)
                for toolset, tools in self.__all_available_tools.items()
            }
        except BaseError:
            raise
        except Exception as e:
            raise BaseError(
                ErrorCode.INTERNAL,
                "Failed to get tool info.",
                cause=e,
            ) from e

    def get_tools_description(self, toolset: str | None) -> dict[str, str]:
        try:
            if toolset:
                if toolset not in self.__all_available_tools:
                    raise BaseError(
                        ErrorCode.NOT_FOUND,
                        f"No tools registered for toolset {toolset!r}.",
                    )
                return {
                    name: tooldef.description
                    for name, tooldef in self.__all_available_tools[toolset].items()
                }
            return {
                name: tooldef.description
                for tools in self.__all_available_tools.values()
                for name, tooldef in tools.items()
            }
        except BaseError:
            raise
        except Exception as e:
            raise BaseError(
                ErrorCode.INTERNAL,
                "Failed to get tool descriptions.",
                details={"toolset": toolset},
                cause=e,
            ) from e

    def get_tool_schema(self, toolset: str, tool_name: str) -> dict[str, Any]:
        try:
            if not tool_name:
                raise BaseError(ErrorCode.INVALID_ARGUMENT, "tool_name is required.")

            tools = self.__all_available_tools.get(toolset, {})
            if tool_name not in tools:
                raise BaseError(
                    ErrorCode.NOT_FOUND,
                    f"Tool {tool_name!r} not found.",
                    details={"toolset": toolset},
                )
            return tools[tool_name].schema
        except BaseError:
            raise
        except Exception as e:
            raise BaseError(
                ErrorCode.INTERNAL,
                f"Failed to get schema for tool {tool_name!r}.",
                cause=e,
            ) from e

    def get_tool_handler(self, toolset: str, tool_name: str) -> Callable:
        try:
            if not tool_name:
                raise BaseError(ErrorCode.INVALID_ARGUMENT, "tool_name is required.")

            tools = self.__all_available_tools.get(toolset, {})
            if tool_name in tools:
                return tools[tool_name].handler

            raise BaseError(
                ErrorCode.NOT_FOUND,
                f"Tool {tool_name!r} not found.",
                details={"toolset": toolset},
            )
        except BaseError:
            raise
        except Exception as e:
            raise BaseError(
                ErrorCode.INTERNAL,
                f"Failed to get handler for tool {tool_name!r}.",
                details={"toolset": toolset},
                cause=e,
            ) from e


registry = ToolRegistry()
