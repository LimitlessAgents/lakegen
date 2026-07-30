from typing import Callable

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.tool.model import ToolDefinition, ToolArguments


class ToolRegistry:
    """In-memory catalog of tools keyed by name.

    Tool modules call ``register`` at import time (see ``lakegen.tool``), so the
    single module-level ``registry`` is fully populated once imported.
    """

    def __init__(self):
        # Name-mangled to discourage reaching into the store from outside;
        # callers should go through the getter methods below.
        self.__all_available_tools: dict[str, ToolDefinition] = {}

    def register(
        self,
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
        self.__all_available_tools[name] = ToolDefinition(
            name=tool_dict["name"],
            description=tool_dict["description"],
            arguments=tool_dict["arguments"],
            arguments_model=arguments_model,
            handler=handler,
            requires_env=requires_env,
        )

    def list_tool_names(self) -> list[str]:
        try:
            return list(self.__all_available_tools)
        except BaseError:
            raise
        except Exception as e:
            raise BaseError(
                ErrorCode.INTERNAL,
                "Failed to list tool names.",
            ) from e

    def get_all_tools_info(self) -> dict[str, ToolDefinition]:
        try:
            return dict(self.__all_available_tools)
        except BaseError:
            raise
        except Exception as e:
            raise BaseError(
                ErrorCode.INTERNAL,
                "Failed to get tool info.",
            ) from e

    def get_tool_definition(self, tool_name: str) -> ToolDefinition:
        try:
            if not tool_name:
                raise BaseError(ErrorCode.INVALID_ARGUMENT, "tool_name is required.")

            if tool_name not in self.__all_available_tools:
                raise BaseError(
                    ErrorCode.NOT_FOUND,
                    f"Tool {tool_name!r} not found.",
                )
            return self.__all_available_tools[tool_name]
        except BaseError:
            raise
        except Exception as e:
            raise BaseError(
                ErrorCode.INTERNAL,
                f"Failed to get tool definition for {tool_name!r}.",
            ) from e


registry = ToolRegistry()
