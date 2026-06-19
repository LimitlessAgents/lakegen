from pydantic import Field
from typing import Literal, Any, Callable

from dataclasses import dataclass


@dataclass(slots=True)
class ToolDefinition:
    type: Literal["function"] = "function"
    name: str
    description: str
    schema: dict[str, Any]
    handler: Callable
    requires_env: bool


@dataclass(slots=True)
class ToolOutput:
    ok: bool
    response: Any = None
    error: dict[str, Any] = Field(default_factory=dict)
