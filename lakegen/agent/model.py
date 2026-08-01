from dataclasses import dataclass, field
from enum import StrEnum

from lakegen.inference import Message

class StopReason(StrEnum):
    COMPLETED = "completed"
    MAX_ITERATIONS_EXCEEDED = "max_iterations_exceeded"
    KEYBOARD_INTERRUPTION = "keyboard_interruption"
    INTERNAL_ERROR = "internal_error"


@dataclass
class Conversation:
    messages: list[Message] = field(default_factory=list)

@dataclass(frozen=True)
class AgentLoopResult:
    final_message: str
    transcript: Conversation
    stop_reason: StopReason

@dataclass(frozen=True)
class AgentConfig:
    model: str
    system_prompt: str
    provider: str
    max_turns: int