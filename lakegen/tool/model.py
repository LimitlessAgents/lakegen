from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable


@runtime_checkable
class ToolParams(Protocol):
    """Params provider a tool registers.

    Any Pydantic ``BaseModel`` subclass satisfies this, as does a lightweight
    adapter that delegates to a ``TypeAdapter`` (e.g. a discriminated union).
    Validation returns the concrete parsed object; the schema is advertised to
    the agent.
    """

    def model_validate(self, data: Any, /) -> Any: ...

    def model_json_schema(self) -> dict[str, Any]: ...


@dataclass(slots=True)
class ToolDefinition:
    """A registered tool: what the agent sees plus how to run it.

    ``params`` is the JSON Schema shown to the agent, while ``params_model`` is
    the provider used at call time to validate raw input. They are derived from
    the same source at registration but kept separate so ``to_dict`` can expose
    the agent-facing view without leaking the handler or validator.
    """

    name: str
    description: str
    params: dict[str, Any]
    handler: Callable = field(repr=False, compare=False)
    params_model: ToolParams = field(repr=False, compare=False)
    # Whether the tool needs external environment/config to be present.
    requires_env: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Agent-facing view: name, description, and input schema only."""
        return {
            "name": self.name,
            "description": self.description,
            "params": self.params,
        }


@dataclass(slots=True)
class ToolOutput:
    """Result of one tool call.

    On success ``ok`` is True and ``response`` holds the handler's return value;
    on failure ``ok`` is False and ``error`` holds a serialized ``BaseError``.
    Failures are reported here rather than raised so the agent receives
    structured feedback it can act on.
    """

    tool_name: str
    ok: bool
    response: Any = None
    error: dict[str, Any] = field(default_factory=dict)
