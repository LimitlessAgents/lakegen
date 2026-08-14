from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Depends, Request

from lakegen.api.auth.authenticator import Authenticator, Principal
from lakegen.api.auth.local import LocalAuth
from lakegen.api.run.local import LocalRunAdapter
from lakegen.api.run.runner import AgentRunner
from lakegen.core.catalog.service import CatalogService, catalog_service


@dataclass
class AppState:
    authenticator: Authenticator
    agent_runner: AgentRunner
    catalogs: CatalogService
    cors_origins: list[str]
    max_in_flight_turns: int


def default_cors_origins() -> list[str]:
    raw = os.environ.get(
        "LAKEGEN_CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173",
    )
    return [o.strip() for o in raw.split(",") if o.strip()]


def default_max_in_flight_turns() -> int:
    raw = os.environ.get("LAKEGEN_MAX_IN_FLIGHT_TURNS", "8")
    try:
        return max(1, int(raw))
    except ValueError:
        return 8


def build_app_state(
    *,
    authenticator: Authenticator | None = None,
    agent_runner: AgentRunner | None = None,
    catalogs: CatalogService | None = None,
    cors_origins: list[str] | None = None,
    max_in_flight_turns: int | None = None,
) -> AppState:
    return AppState(
        # TODO(real-auth): LocalAuth trusts X-User with no verification. Replace
        # with a verified Authenticator before any shared/multi-tenant deployment.
        authenticator=authenticator if authenticator is not None else LocalAuth(),
        agent_runner=agent_runner if agent_runner is not None else LocalRunAdapter(),
        catalogs=catalogs if catalogs is not None else catalog_service,
        cors_origins=(
            cors_origins if cors_origins is not None else default_cors_origins()
        ),
        max_in_flight_turns=(
            max_in_flight_turns
            if max_in_flight_turns is not None
            else default_max_in_flight_turns()
        ),
    )


def get_app_state(request: Request) -> AppState:
    return request.app.state.lakegen


def get_authenticator(state: AppState = Depends(get_app_state)) -> Authenticator:
    return state.authenticator


def get_agent_runner(state: AppState = Depends(get_app_state)) -> AgentRunner:
    return state.agent_runner


def get_catalogs(state: AppState = Depends(get_app_state)) -> CatalogService:
    return state.catalogs


def require_principal(
    request: Request,
    authenticator: Authenticator = Depends(get_authenticator),
) -> Principal:
    return authenticator.resolve(request)
