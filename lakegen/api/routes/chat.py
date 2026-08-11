from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from queue import Queue

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sse_starlette.sse import EventSourceResponse

from lakegen.api.auth.authenticator import Principal
from lakegen.api.deps import AppState, get_agent_runner, get_app_state, require_principal
from lakegen.api.run.runner import AgentEvent, AgentEventType, AgentRunner
from lakegen.core.error.base import BaseError

router = APIRouter(prefix="/v1/sessions", tags=["chat"])

_turn_semaphore: asyncio.Semaphore | None = None
_turn_semaphore_limit: int | None = None


class TurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    catalog_name: str | None = None
    model: str = Field(default="openrouter/free")
    provider: str = Field(default="openai")


def _get_turn_semaphore(limit: int) -> asyncio.Semaphore:
    global _turn_semaphore, _turn_semaphore_limit
    if _turn_semaphore is None or _turn_semaphore_limit != limit:
        _turn_semaphore = asyncio.Semaphore(limit)
        _turn_semaphore_limit = limit
    return _turn_semaphore


def _sse_event(event: AgentEvent) -> dict[str, str]:
    return {
        "event": event.type.value,
        "data": json.dumps(event.data),
    }


@router.post("/{session_id}/turns")
async def run_turn(
    session_id: str,
    body: TurnRequest,
    request: Request,
    _principal: Principal = Depends(require_principal),
    agent_runner: AgentRunner = Depends(get_agent_runner),
    state: AppState = Depends(get_app_state),
) -> EventSourceResponse:
    # Sync queue so worker-thread on_event callbacks and the async sentinel
    # share one ordered channel (asyncio.Queue + call_soon_threadsafe races).
    events: Queue[AgentEvent | None] = Queue()
    sem = _get_turn_semaphore(state.max_in_flight_turns)

    def on_event(event: AgentEvent) -> None:
        events.put(event)

    async def run_in_background() -> None:
        await sem.acquire()
        try:
            try:
                await asyncio.to_thread(
                    agent_runner.run_turn,
                    session_id,
                    body.text,
                    catalog_name=body.catalog_name,
                    model=body.model,
                    provider=body.provider,
                    on_event=on_event,
                )
            except BaseError as exc:
                events.put(
                    AgentEvent(type=AgentEventType.ERROR, data=exc.to_dict())
                )
            except Exception as exc:  # noqa: BLE001
                events.put(
                    AgentEvent(
                        type=AgentEventType.ERROR,
                        data={"code": "INTERNAL", "message": str(exc)},
                    )
                )
        finally:
            sem.release()
            events.put(None)

    async def event_stream() -> AsyncIterator[dict[str, str]]:
        task = asyncio.create_task(run_in_background())
        try:
            while True:
                if await request.is_disconnected():
                    break
                item = await asyncio.to_thread(events.get)
                if item is None:
                    break
                yield _sse_event(item)
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    return EventSourceResponse(event_stream())
