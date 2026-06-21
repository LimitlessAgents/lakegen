from typing import Literal, Any, Callable

from dataclasses import dataclass, field


@dataclass(slots=True)
class ToolDefinition:
    name: str
    description: str
    schema: dict[str, Any]
    handler: Callable
    requires_env: bool


@dataclass(slots=True)
class ToolOutput:
    ok: bool
    response: Any = None
    error: dict[str, Any] = field(default_factory=dict)
