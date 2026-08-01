from dataclasses import dataclass, field
from datetime import datetime

from lakegen.agent import AgentConfig, Conversation


@dataclass
class SessionState:
    id: int
    config: AgentConfig
    parent_id: int | None = None
    children: list[int] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    messages: Conversation = field(default_factory=Conversation)
