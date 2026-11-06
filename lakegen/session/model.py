from dataclasses import dataclass, field
from datetime import datetime

from lakegen.agent import AgentConfig, AgentLoopResult, Conversation


@dataclass(frozen=True)
class SessionInfo:
    id: str
    name: str | None
    created_at: datetime
    catalog_name: str | None


@dataclass
class SessionState:
    id: str
    config: AgentConfig
    owner_id: str
    catalog_name: str | None = None
    closed: bool = False
    parent_id: str | None = None
    children: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    messages: Conversation = field(default_factory=Conversation)
    context_tokens: int | None = None  # last known context size


@dataclass(frozen=True)
class SessionTurnResult:
    id: int
    result: AgentLoopResult


@dataclass(frozen=True)
class AgentTurnInfo:
    id: str
    created_at: datetime
    result: dict[str, object]


@dataclass(frozen=True)
class TokenBudget:
    total: int
    system_prompt: int
    tool_definitions: int
    conversation: int