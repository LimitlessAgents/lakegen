from dataclasses import dataclass
from typing import Any
from enum import StrEnum

from lakegen.tool.model import ToolDefinition


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ToolCall:
    """One tool the model wants to run."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class Message:
    """One turn in the conversation."""

    role: Role
    content: str | None = None
    tool_calls: list[ToolCall] | None = None  # assistant asked to run tools
    tool_call_id: str | None = None  # tool result → which call this answers
    tool_name: str | None = None  # tool result → tool name


@dataclass
class ChatRequest:
    """What we send to a provider."""

    model: str
    system_prompt: str
    messages: list[Message]
    tools: list[ToolDefinition]
    temperature: float


@dataclass
class ChatResponse:
    """What we get back from a provider."""

    message: Message
    tokens: TokenUsage | None = None
