from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel


@dataclass(slots=True)
class ToolDefinition:
    name: str
    description: str
    params: dict[str, dict[str, Any]]
    handler: Callable = field(repr=False, compare=False)
    params_model: type[BaseModel] = field(repr=False, compare=False)
    requires_env: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "params": self.params,
        }


@dataclass(slots=True)
class ToolOutput:
    tool_name: str
    ok: bool
    response: Any = None
    error: dict[str, Any] = field(default_factory=dict)
