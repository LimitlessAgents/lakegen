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

@dataclass(frozen=True)
class Environment:
    tool_registry: ToolRegistry
    catalog_service: CatalogService
    inference_registry: InferenceRegistry
    inference_router: Router
    persistence: PostgresPersistence
    session_repository: SessionRepository
    agent_turn_repository: AgentTurnRepository

    @classmethod
    def default(cls) -> "Environment":
        return cls(
            tool_reg,
            catalog_service,
            inference_reg,
            inference_rout,
            persistence_def,
            session_repository,
            agent_turn_repository,
        )
