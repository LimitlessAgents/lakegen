from __future__ import annotations

from dataclasses import dataclass

from lakegen.core.catalog.service import CatalogService, catalog_service
from lakegen.core.persistence import (
    PostgresPersistence,
    persistence as persistence_def,
)
from lakegen.core.persistence.repository.agent_turn_repository import (
    AgentTurnRepository,
    agent_turn_repository,
)
from lakegen.core.persistence.repository.compression_repository import (
    CompressionRepository,
    compression_repository,
)
from lakegen.core.persistence.repository.session_repository import (
    SessionRepository,
    session_repository,
)
from lakegen.inference import (
    InferenceRegistry,
    Router,
    registry as inference_reg,
    router as inference_rout,
)
from lakegen.tool import (
    ToolRegistry,
    registry as tool_reg,
)
from lakegen.session.context import ContextEngine
from lakegen.session.model import TokenBudget


def calculate_token_budget(total_budget: int = 200_000) -> TokenBudget:
    return TokenBudget(
        total=total_budget,
        system_prompt=int(total_budget * 0.1),
        tool_definitions=int(total_budget * 0.1),
        conversation=int(total_budget * 0.8),
    )


@dataclass(frozen=True)
class Environment:
    tool_registry: ToolRegistry
    catalog_service: CatalogService
    inference_registry: InferenceRegistry
    inference_router: Router
    persistence: PostgresPersistence
    context_engine: ContextEngine
    session_repository: SessionRepository
    agent_turn_repository: AgentTurnRepository
    compression_repository: CompressionRepository
    token_budget: TokenBudget

    @classmethod
    def default(cls) -> Environment:
        return cls(
            tool_reg,
            catalog_service,
            inference_reg,
            inference_rout,
            persistence_def,
            ContextEngine(),
            session_repository,
            agent_turn_repository,
            compression_repository,
            calculate_token_budget(),
        )
