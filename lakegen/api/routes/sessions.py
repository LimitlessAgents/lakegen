from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field

from lakegen.api.auth.authenticator import Principal
from lakegen.api.deps import get_agent_runner, require_principal
from lakegen.api.run.runner import AgentRunner

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


class CreateSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str


@router.post("", status_code=status.HTTP_201_CREATED)
def create_session(
    _principal: Principal = Depends(require_principal),
    agent_runner: AgentRunner = Depends(get_agent_runner),
) -> CreateSessionResponse:
    session_id = agent_runner.create_session(owner_id=_principal.id)
    return CreateSessionResponse(id=session_id)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: str,
    principal: Principal = Depends(require_principal),
    agent_runner: AgentRunner = Depends(get_agent_runner),
) -> Response:
    agent_runner.delete_session(session_id, owner_id=principal.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
