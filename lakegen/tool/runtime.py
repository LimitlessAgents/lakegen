import json
from typing import Any

from pydantic import ValidationError

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.tool.model import ToolOutput, ToolCall
from lakegen.tool.registry import registry


class ToolRuntime:
    """Validate tool input and call the registered handler.

    Every call returns a ``ToolOutput`` instead of raising, so a failure in one
    tool never aborts a batch and the agent always gets a structured result.
    """

    def dispatch(self, toolset: str, tools_to_call: list[ToolCall]) -> list[ToolOutput]:
        """Run each requested tool and collect one ``ToolOutput`` per call."""
        if not tools_to_call:
            return []
        return [
            self._run_one(toolset, tool.name, tool.arguments)
            for tool in tools_to_call
        ]

    def _run_one(self, toolset: str, name: str, arguments: dict[str, Any]) -> ToolOutput:
        try:
            if not isinstance(arguments, dict):
                if isinstance(arguments, (str, bytes, bytearray)):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        return ToolOutput(
                            tool_name=name,
                            ok=False,
                            error=BaseError(
                                ErrorCode.INVALID_TYPE,
                                "Tool arguments must be a dict.",
                                details={"got_type": type(arguments).__name__},
                            ).to_dict()
                        )
                if not isinstance(arguments, dict):
                    return ToolOutput(
                        tool_name=name,
                        ok=False,
                        error=BaseError(
                            ErrorCode.INVALID_TYPE,
                            "Tool arguments must be a dict.",
                            details={"got_type": type(arguments).__name__},
                        ).to_dict()
                    )

            tool = registry.get_tool_definition(toolset, name)
            # Validation turns raw input into the concrete arguments object the
            # handler expects (e.g. a specific catalog spec for add_catalog).
            validated = tool.arguments_model.model_validate(arguments)
            result = tool.handler(validated)

            # Safety net: verify the result is JSON-serializable before handing
            # it back. A tool that forgets to normalize its output gets caught
            # here rather than producing an unreadable response to the agent.
            try:
                json.dumps(result)
            except (TypeError, ValueError) as e:
                raise BaseError(
                    ErrorCode.INTERNAL,
                    f"Tool {name!r} returned a non-serializable result.",
                    cause=e,
                )

            return ToolOutput(
                tool_name=name,
                ok=True,
                response=result,
            )
        # Application errors already carry a structured, agent-readable payload.
        except BaseError as e:
            return ToolOutput(tool_name=name, ok=False, error=e.to_dict())
        # Bad agent input: surface the field-level Pydantic errors so it can retry.
        except ValidationError as e:
            return ToolOutput(
                tool_name=name,
                ok=False,
                error={
                    "code": ErrorCode.INVALID_ARGUMENT.value,
                    "message": f"Invalid arguments for tool {name!r}.",
                    "details": {"errors": e.errors()},
                },
            )
        # Anything unexpected: wrap as INTERNAL so the batch still returns cleanly.
        # Attach the original as the cause so its type/message survive in to_dict.
        except Exception as e:
            return ToolOutput(
                tool_name=name,
                ok=False,
                error=BaseError(
                    ErrorCode.INTERNAL,
                    f"Unexpected error while running tool {name!r}.",
                    cause=e,
                ).to_dict()
            )


runtime = ToolRuntime()
