from pydantic import BaseModel, Field
from typing import Literal, Any, Callable


class ToolParameters(BaseModel):
    type: Literal["object"] = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)
    additionalProperties: bool = False


class ToolDefinition(BaseModel):
    type: Literal["function"] = "function"
    name: str
    description: str
    parameters: ToolParameters = Field(default_factory=ToolParameters)
    handler: Callable


class ToolOutput(BaseModel):
    ok: bool
    response: Any = None
    error: dict[str, Any] = Field(default_factory=dict)
