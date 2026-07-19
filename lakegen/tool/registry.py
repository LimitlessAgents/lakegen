from typing import Any, Callable

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.tool.model import ToolDefinition, ToolArguments


class ToolRegistry:
    """In-memory catalog of tools, grouped by toolset.

    Tools are stored two levels deep: ``toolset -> tool_name -> ToolDefinition``.
    Tool modules call ``register`` at import time (see ``lakegen.tool``), so the
    single module-level ``registry`` is fully populated once imported.
    """

    def __init__(self):
        # Name-mangled to discourage reaching into the store from outside;
        # callers should go through the getter methods below.
        self.__all_available_tools: dict[str, dict[str, ToolDefinition]] = {}

    def register(
        self,
        toolset: str,
        name: str,
        *,
        description: str,
        arguments_model: ToolArguments,
        handler: Callable,
        requires_env: bool = False,
    ):
        """Build a tool's schema from ``arguments_model`` and store its definition."""
        from lakegen.tool.util.schema import arguments_model_to_tool_dict

        # Fail loudly at registration (import time) if a tool is wired up wrong:
        # this is a developer error, not something an agent should ever see.
        if not isinstance(arguments_model, ToolArguments):
            raise TypeError(
                "arguments_model must provide 'model_validate' and 'model_json_schema'."
            )

        tool_dict = arguments_model_to_tool_dict(name, description, arguments_model)
        self.__all_available_tools.setdefault(toolset, {})[name] = ToolDefinition(
            name=tool_dict["name"],
            description=tool_dict["description"],
            arguments=tool_dict["arguments"],
            arguments_model=arguments_model,
            handler=handler,
            requires_env=requires_env,
        )

    def list_tool_names(self) -> list[str]:
        # Pattern used by every getter below: let intentional BaseErrors through
        # unchanged, but wrap any unexpected failure as INTERNAL so callers only
        # ever have to handle BaseError.
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
            ) from e

    def get_tool_definition(self, toolset: str, tool_name: str) -> ToolDefinition:
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
            return tools[tool_name]
        except BaseError:
            raise
        except Exception as e:
            raise BaseError(
                ErrorCode.INTERNAL,
                f"Failed to get tool definition for {tool_name!r}.",
            ) from e

    def get_tool_schema(self, toolset: str, tool_name: str) -> dict[str, Any]:
        return self.get_tool_definition(toolset, tool_name).to_dict()

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
            ) from e


registry = ToolRegistry()
