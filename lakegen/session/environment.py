from dataclasses import dataclass

from lakegen.core.catalog.service import CatalogService, catalog_service
from lakegen.core.persistence import (
    PostgresPersistence,
    persistence as persistence_def,
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

    @classmethod
    def default(cls) -> "Environment":
        return cls(
            tool_reg,
            catalog_service,
            inference_reg,
            inference_rout,
            persistence_def,
        )
