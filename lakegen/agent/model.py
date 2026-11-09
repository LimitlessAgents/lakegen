from dataclasses import dataclass, field
from enum import StrEnum

from lakegen.inference import Message


class StopReason(StrEnum):
    COMPLETED = "completed"
    MAX_ITERATIONS_EXCEEDED = "max_iterations_exceeded"
    CANCELLED = "cancelled"
    INTERNAL_ERROR = "internal_error"


class CompressionScope(StrEnum):
    """Which part of the context a compression replaced."""

    HISTORY = "history"  # everything before the current turn
    TURN = "turn"        # completed iterations of the current turn


@dataclass(frozen=True)
class CompressionEvent:
    """Audit record of one compaction, stored with the turn it changed."""

    scope: CompressionScope
    summary: str
    replaced_messages: int


@dataclass
class Conversation:
    messages: list[Message] = field(default_factory=list)


@dataclass(frozen=True)
class AgentLoopResult:
    final_message: str
    # The turn as the model saw it, including any summary or trimming. This is
    # the canonical history: its token counts describe exactly this prefix.
    turn_messages: Conversation
    stop_reason: StopReason
    compression_events: tuple[CompressionEvent, ...] = ()
    context_tokens: int | None = None
    context_source: str | None = None


class AgentLoopFailure(Exception):
    """Unexpected loop failure carrying the partial turn for persistence."""

    def __init__(self, result: AgentLoopResult, error: Exception) -> None:
        self.result = result
        self.error = error
        super().__init__(str(error))


@dataclass(frozen=True)
class AgentConfig:
    model: str
    system_prompt: str
    provider: str
    max_turns: int
    # Endpoint for OpenAI-compatible providers; ``None`` keeps the SDK default.
    base_url: str | None = None
