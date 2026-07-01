from typing import Any

from pydantic import ValidationError

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.tool.model import ToolOutput
from lakegen.tool.registry import registry


class ToolRuntime:
    """Validate tool input and call the registered handler."""

    def invoke(self, toolset: str, tools_to_call: dict[str, Any]) -> list[ToolOutput]:
        if not tools_to_call:
            return []
        return [
            self.use_tool(toolset, name, params)
            for name, params in tools_to_call.items()
        ]

    def use_tool(self, toolset: str, name: str, params: dict[str, Any]) -> ToolOutput:
        try:
            if not isinstance(params, dict):
                raise BaseError(
                    ErrorCode.INVALID_TYPE,
                    "Tool parameters must be a dict.",
                    details={"got_type": type(params).__name__},
                )

            tool = registry.get_tool_definition(toolset, name)
            validated = tool.params_model.model_validate(params)
            result = tool.handler(validated)
            return ToolOutput(
                tool_name=name,
                ok=True,
                response=result,
            )
        except BaseError as e:
            return ToolOutput(tool_name=name, ok=False, error=e.to_dict())
        except ValidationError as e:
            return ToolOutput(
                tool_name=name,
                ok=False,
                error={
                    "code": ErrorCode.INVALID_ARGUMENT.value,
                    "message": f"Invalid parameters for tool {name!r}.",
                    "details": {"errors": e.errors()},
                },
            )
        except Exception as e:
            return ToolOutput(
                tool_name=name,
                ok=False,
                error={"code": ErrorCode.INTERNAL.value, "message": str(e)},
            )


tool_runtime = ToolRuntime()
