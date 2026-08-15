"""HTTP request/response models.

Write bodies reuse domain models (``CatalogSpec``). This module holds shapes
that exist only on the wire: secret-stripped reads, SSE payloads, and the
error envelope.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from lakegen.agent import StopReason
from lakegen.api.run.runner import AgentEventType
from lakegen.core.error.code import ErrorCode


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorBody(APIModel):
    """Client-facing error returned by REST and SSE boundaries."""

    code: ErrorCode
    message: str


class CatalogResponse(APIModel):
    """Non-secret catalog view. Write path is ``CatalogSpec``."""

    name: str
    connected: bool
    lakehouse: str | None = None
    catalog_type: str | None = None
    warehouse: str | None = None


class CreateSessionResponse(APIModel):
    id: str


class TurnRequest(APIModel):
    text: str = Field(min_length=1)
    catalog_name: str | None = None
    model: str = Field(default="openrouter/free")
    provider: str = Field(default="openai")


class TextDeltaData(APIModel):
    text: str


class TurnDoneData(APIModel):
    final_message: str
    stop_reason: StopReason


class TextDeltaEvent(APIModel):
    type: Literal[AgentEventType.TEXT_DELTA] = AgentEventType.TEXT_DELTA
    data: TextDeltaData


class TurnDoneEvent(APIModel):
    type: Literal[AgentEventType.TURN_DONE] = AgentEventType.TURN_DONE
    data: TurnDoneData


class ErrorEvent(APIModel):
    type: Literal[AgentEventType.ERROR] = AgentEventType.ERROR
    data: ErrorBody


StreamEvent = Annotated[
    TextDeltaEvent | TurnDoneEvent | ErrorEvent,
    Field(discriminator="type"),
]

stream_event_adapter: TypeAdapter[StreamEvent] = TypeAdapter(StreamEvent)
