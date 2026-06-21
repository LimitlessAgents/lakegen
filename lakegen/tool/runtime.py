from typing import Any

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.tool.model import ToolOutput
from lakegen.tool.registry import registry


class ToolRuntime:
    def invoke(self, toolset: str, tools_to_call: dict[str, Any]) -> list[ToolOutput]:
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
            schema = registry.get_tool_schema(toolset, name)
            p = schema.get("parameters", {})
            if missing := [k for k in p.get("required", []) if k not in params]:
                raise BaseError(ErrorCode.INVALID_ARGUMENT, "Missing required parameters.", details={"missing": missing})
            # if p.get("additionalProperties") is False and (extra := set(params) - p.get("properties", {})):
            #     raise BaseError(ErrorCode.INVALID_ARGUMENT, "Unexpected parameters.", details={"extra": list(extra)})

            handler = registry.get_tool_handler(toolset, name)
            result = handler(params)
            return ToolOutput(
                ok=True,
                response=result,
            )
        except BaseError as e:
            return ToolOutput(ok=False, error=e.to_dict())
        except Exception as e:
            return ToolOutput(
                ok=False,
                error={"code": ErrorCode.INTERNAL.value, "message": str(e)},
            )


tool_runtime = ToolRuntime()
