from typing import Any, Callable

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.tool.model import ToolDefinition


class ToolRegistry:
    def __init__(self):
        self.__all_available_tools: dict[str, dict[str, ToolDefinition]] = {}

    def register(
        self,
        kind: str,
        name: str,
        schema: dict[str, Any],
        handler: Callable,
        requires_env: bool = False,
        description: str = ""
        ):
        self.__all_available_tools.setdefault(kind, {})[name] = ToolDefinition(
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
                kind: dict(tools)
                for kind, tools in self.__all_available_tools.items()
            }
        except BaseError:
            raise
        except Exception as e:
            raise BaseError(
                ErrorCode.INTERNAL,
                "Failed to get tool info.",
                cause=e,
            ) from e

    def get_tools_description(self, kind: str | None) -> dict[str, str]:
        try:
            if kind:
                if kind not in self.__all_available_tools:
                    raise BaseError(
                        ErrorCode.NOT_FOUND,
                        f"No tools registered for kind {kind!r}.",
                    )
                return {
                    name: tooldef.description
                    for name, tooldef in self.__all_available_tools[kind].items()
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
                details={"kind": kind},
                cause=e,
            ) from e

    def get_tool_schema(self, kind: str, tool_name: str) -> dict[str, Any]:
        try:
            if not tool_name:
                raise BaseError(ErrorCode.INVALID_ARGUMENT, "tool_name is required.")

            tools = self.__all_available_tools.get(kind, {})
            if tool_name not in tools:
                raise BaseError(
                    ErrorCode.NOT_FOUND,
                    f"Tool {tool_name!r} not found.",
                    details={"kind": kind},
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

    def get_tool_handler(self, kind: str, tool_name: str) -> Callable:
        try:
            if not tool_name:
                raise BaseError(ErrorCode.INVALID_ARGUMENT, "tool_name is required.")

            tools = self.__all_available_tools.get(kind, {})
            if tool_name in tools:
                return tools[tool_name].handler

            raise BaseError(
                ErrorCode.NOT_FOUND,
                f"Tool {tool_name!r} not found.",
                details={"kind": kind},
            )
        except BaseError:
            raise
        except Exception as e:
            raise BaseError(
                ErrorCode.INTERNAL,
                f"Failed to get handler for tool {tool_name!r}.",
                details={"kind": kind},
                cause=e,
            ) from e


registry = ToolRegistry()
