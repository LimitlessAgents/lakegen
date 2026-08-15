from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lakegen.api.auth.authenticator import Authenticator
from lakegen.api.deps import build_app_state
from lakegen.api.errors import register_exception_handlers
from lakegen.api.openapi import install_openapi
from lakegen.api.routes import catalogs, chat, health, sessions
from lakegen.api.run.runner import AgentRunner
from lakegen.core.catalog.service import CatalogService

from dotenv import load_dotenv
load_dotenv()


def create_app(
    *,
    authenticator: Authenticator | None = None,
    agent_runner: AgentRunner | None = None,
    catalogs_service: CatalogService | None = None,
    cors_origins: list[str] | None = None,
    max_in_flight_turns: int | None = None,
) -> FastAPI:
    """Build the LakeGen BFF application.

    Pass ``authenticator`` / ``agent_runner`` / ``catalogs_service`` to override
    defaults (tests).
    """
    state = build_app_state(
        authenticator=authenticator,
        agent_runner=agent_runner,
        catalogs=catalogs_service,
        cors_origins=cors_origins,
        max_in_flight_turns=max_in_flight_turns,
    )

    app = FastAPI(title="LakeGen", version="0.1.0")
    app.state.lakegen = state

    app.add_middleware(
        CORSMiddleware,
        allow_origins=state.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(catalogs.router)
    app.include_router(sessions.router)
    app.include_router(chat.router)

    install_openapi(app)

    return app


app = create_app()
