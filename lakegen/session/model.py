from dataclasses import dataclass, field
from datetime import datetime

from lakegen.agent import AgentConfig, AgentLoopResult, Conversation


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


@dataclass(frozen=True)
class SessionTurnResult:
    id: str
    result: AgentLoopResult
