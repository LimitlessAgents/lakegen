from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from queue import Queue

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from lakegen.api.auth.authenticator import Principal
from lakegen.api.deps import AppState, get_agent_runner, get_app_state, require_principal
from lakegen.api.errors import error_body_for
from lakegen.api.responses import SERVICE_ERROR_RESPONSES
from lakegen.api.run.runner import AgentEvent, AgentEventType, AgentRunner
from lakegen.api.schema import ErrorBody, TurnRequest
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode

router = APIRouter(
    prefix="/v1/sessions",
    tags=["chat"],
    responses=SERVICE_ERROR_RESPONSES,
)

_turn_semaphore: asyncio.Semaphore | None = None
_turn_semaphore_limit: int | None = None


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
    principal: Principal = Depends(require_principal),
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
                    owner_id=principal.id,
                    catalog_name=body.catalog_name,
                    model=body.model,
                    provider=body.provider,
                    on_event=on_event,
                )
            except BaseError as exc:
                events.put(
                    AgentEvent(
                        type=AgentEventType.ERROR,
                        data=error_body_for(exc).model_dump(mode="json"),
                    )
                )
            except Exception:  # noqa: BLE001
                events.put(
                    AgentEvent(
                        type=AgentEventType.ERROR,
                        data=ErrorBody(
                            code=ErrorCode.INTERNAL,
                            message="An unexpected error occurred."
                        ).model_dump(mode="json"),
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
            # TODO(cancel-in-flight-turns): When turns become cancellable, cancel
            # the worker here on disconnect (and roll back or avoid committing
            # conversation mutations the client never saw). Until then: do not
            # cancel — asyncio.to_thread is not stopped by CancelledError, so
            # cancelling would release the semaphore while the turn still runs.
            # Hold the slot until the worker finishes; SSE just stops yielding.
            await asyncio.shield(task)

    return EventSourceResponse(event_stream())
