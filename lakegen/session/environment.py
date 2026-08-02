from dataclasses import dataclass

from lakegen.core.connection import (
    ConnectionRegistry,
    conreg as connection_reg,
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
    connection_registry: ConnectionRegistry
    inference_registry: InferenceRegistry
    inference_router: Router

    @classmethod
    def default(cls) -> "Environment":
        return cls(
            tool_reg,
            connection_reg,
            inference_reg,
            inference_rout,
        )
