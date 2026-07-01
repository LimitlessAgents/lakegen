from typing import Any, Callable

from pydantic import BaseModel

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
        *,
        description: str,
        params_model: type[BaseModel],
        handler: Callable,
        requires_env: bool = False,
    ):
        from lakegen.tool.util.schema import params_model_to_tool_dict

        if not issubclass(params_model, BaseModel):
            raise BaseError(
                ErrorCode.INVALID_ARGUMENT,
                "params_model must be a Pydantic BaseModel subclass.",
            )

        tool_dict = params_model_to_tool_dict(name, description, params_model)
        self.__all_available_tools.setdefault(toolset, {})[name] = ToolDefinition(
            name=tool_dict["name"],
            description=tool_dict["description"],
            params=tool_dict["params"],
            params_model=params_model,
            handler=handler,
            requires_env=requires_env,
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
                cause=e,
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
                cause=e,
            ) from e


registry = ToolRegistry()
