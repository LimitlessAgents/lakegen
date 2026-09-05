import json
import threading

from pydantic import ValidationError

from lakegen.core.catalog.service import CatalogService, catalog_service
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.tool.model import ToolCall, ToolOutput
from lakegen.tool.registry import ToolRegistry, registry as default_registry


class ToolRuntime:
    """Validate tool input and call the registered handler.

    Every call returns a ``ToolOutput`` instead of raising, so a failure in one
    tool never aborts a batch and the agent always gets a structured result.

    The runtime is also the authority for which tools a session may advertise
    to the model (via ``list_definitions``) and execute (via ``dispatch``).

    Catalog-scoped sessions always inject ``catalog_name`` as ``name`` on tool
    arguments before validation.
    """

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        catalogs: CatalogService = catalog_service,
    ) -> None:
        self._registry = registry if registry is not None else default_registry
        self._catalogs = catalogs

    def list_definitions(self):
        """Tools this runtime will expose to the model."""
        return list(self._registry.get_all_tools_info().values())

    def dispatch(
        self,
        tools_to_call: list[ToolCall],
        *,
        catalog_name: str,
        cancel_event: threading.Event | None = None,
    ) -> list[ToolOutput]:
        """Run each requested tool and collect one ``ToolOutput`` per call."""
        if not tools_to_call:
            return []
        outputs: list[ToolOutput] = []
        for call in tools_to_call:
            if cancel_event is not None and cancel_event.is_set():
                break
            outputs.append(self._run_one(call, catalog_name=catalog_name))
        return outputs

    def _run_one(self, call: ToolCall, *, catalog_name: str) -> ToolOutput:

        call_id = call.id
        name = call.name
        arguments = call.arguments

        try:
            if not isinstance(arguments, dict):
                if isinstance(arguments, (str, bytes, bytearray)):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        return ToolOutput(
                            tool_name=name,
                            tool_call_id=call_id,
                            ok=False,
                            error=BaseError(
                                ErrorCode.INVALID_TYPE,
                                "Tool arguments must be a dict.",
                                details={"got_type": type(arguments).__name__},
                            ).to_dict(),
                        )
                if not isinstance(arguments, dict):
                    return ToolOutput(
                        tool_name=name,
                        tool_call_id=call_id,
                        ok=False,
                        error=BaseError(
                            ErrorCode.INVALID_TYPE,
                            "Tool arguments must be a dict.",
                            details={"got_type": type(arguments).__name__},
                        ).to_dict(),
                    )

            tool = self._registry.get_tool_definition(name)
            fields = getattr(tool.arguments_model, "model_fields", None)
            if fields is not None and "name" in fields:
                arguments = {**arguments, "name": catalog_name}
            validated = tool.arguments_model.model_validate(arguments)
            if tool.requires_catalog:
                catalog = self._catalogs.get_connection(catalog_name)
                result = tool.handler(validated, catalog)
            else:
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
                tool_call_id=call_id,
                ok=True,
                response=result,
            )
        # Application errors already carry a structured, agent-readable payload.
        except BaseError as e:
            return ToolOutput(
                tool_name=name,
                tool_call_id=call_id,
                ok=False,
                error=e.to_dict(),
            )
        # Bad agent input: surface the field-level Pydantic errors so it can retry.
        except ValidationError as e:
            return ToolOutput(
                tool_name=name,
                tool_call_id=call_id,
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
                tool_call_id=call_id,
                ok=False,
                error=BaseError(
                    ErrorCode.INTERNAL,
                    f"Unexpected error while running tool {name!r}.",
                    cause=e,
                ).to_dict(),
            )


runtime = ToolRuntime()
