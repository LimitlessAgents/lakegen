from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING

from lakegen.agent.model import (
    AgentConfig,
    AgentLoopFailure,
    AgentLoopResult,
    CompressionEvent,
    CompressionScope,
    Conversation,
    StopReason,
)
from lakegen.agent.policy import ContextPolicy, TurnCompressionState
from lakegen.inference import (
    ChatRequest,
    Message,
    Role,
    Router,
    StreamChunk,
)
from lakegen.inference import (
    router as default_router,
)
from lakegen.tool.model import ToolDefinition, ToolOutput
from lakegen.tool.runtime import ToolRuntime
from lakegen.tool.runtime import runtime as default_tool_runtime

if TYPE_CHECKING:
    from lakegen.session.context import ContextEngine, ContextMeasurement


class AgentLoop:
    def __init__(
        self,
        router: Router | None = None,
        tool_runtime: ToolRuntime | None = None,
        context_engine: ContextEngine | None = None,
    ) -> None:
        self._router = router if router is not None else default_router
        self._tools = tool_runtime if tool_runtime is not None else default_tool_runtime
        self._context = context_engine

    def invoke(
        self,
        agent_config: AgentConfig,
        conversation: Conversation,
        user_text: str,
        *,
        catalog_name: str,
        catalog_switched_from: str | None = None,
        stream: bool = False,
        on_chunk: Callable[[StreamChunk], None] | None = None,
        cancel_event: threading.Event,
        context_policy: ContextPolicy | None = None,
    ) -> AgentLoopResult:
        policy = context_policy if context_policy is not None else ContextPolicy()
        # The only record of this turn. Compression and fitting rewrite it, so
        # the turn restored later is exactly the one the model saw.
        active_turn: list[Message] = []
        turn_compression = TurnCompressionState()
        events: list[CompressionEvent] = []
        turns = 0
        response_text = ""
        streamed_text_parts: list[str] = []
        streamed_tool_calls = None
        assistant_appended = True

        def append_message(message: Message) -> None:
            active_turn.append(message)

        def current_messages() -> list[Message]:
            return [*conversation.messages, *active_turn]

        def measure(
            system_prompt: str,
            tools: list[ToolDefinition],
        ) -> ContextMeasurement | None:
            if self._context is None:
                return None
            return self._context.measure(
                history=conversation,
                turn=Conversation(messages=list(active_turn)),
                system_prompt=system_prompt,
                tools=tools,
            )

        def prepare_turn(system_prompt: str, tools: list[ToolDefinition]) -> None:
            """Compress or trim the current turn until the request fits."""
            nonlocal active_turn
            measurement = measure(system_prompt, tools)
            if measurement is None:
                return

            if turn_compression.needs(measurement.turn, policy):
                try:
                    compression = self._context.compress(
                        CompressionScope.TURN,
                        Conversation(messages=list(active_turn)),
                        router=self._router,
                        provider=agent_config.provider,
                        model=os.getenv("COMPRESSION_MODEL") or agent_config.model,
                        cancel_event=cancel_event,
                        base_url=agent_config.base_url,
                    )
                except Exception:
                    # Summarization is best-effort: a provider failure must not
                    # end an otherwise healthy turn. Emergency fitting below
                    # still bounds the request.
                    compression = None
                if compression is not None:
                    active_turn = list(compression.messages.messages)
                    events.append(compression.event)

                    # Hysteresis measures growth from the new, smaller turn.
                    measurement = measure(system_prompt, tools) or measurement
                    turn_compression.record(measurement.turn)

            if measurement.total > policy.input_budget:
                # History already passed its gate at the turn boundary. If it
                # still does not fit, trim the turn as far as possible rather
                # than knowingly sending an oversized request.
                active_turn = list(
                    self._context.fit(
                        active_turn,
                        budget=policy.input_budget - measurement.history,
                    ).messages
                )

        def finish(stop_reason: StopReason) -> AgentLoopResult:
            resolved_call_ids = {
                message.tool_call_id
                for message in active_turn
                if message.role is Role.TOOL and message.tool_call_id is not None
            }
            for message in tuple(active_turn):
                if message.role is not Role.ASSISTANT:
                    continue
                for tool_call in message.tool_calls or []:
                    if tool_call.id in resolved_call_ids:
                        continue
                    append_message(
                        Message(
                            role=Role.TOOL,
                            content=json.dumps(
                                {
                                    "ok": False,
                                    "response": None,
                                    "error": {
                                        "code": stop_reason.value,
                                        "message": (
                                            "Tool execution did not produce a result "
                                            "before the turn ended."
                                        ),
                                    },
                                }
                            ),
                            tool_call_id=tool_call.id,
                            tool_name=tool_call.name,
                        )
                    )
                    resolved_call_ids.add(tool_call.id)

            terminal_message = {
                StopReason.CANCELLED: (
                    f"Turn stopped by the user after {turns} agent iteration(s)."
                ),
                StopReason.MAX_ITERATIONS_EXCEEDED: (
                    f"Turn stopped after reaching {turns} agent iteration(s)."
                ),
                StopReason.INTERNAL_ERROR: (
                    f"Turn crashed after {turns} agent iteration(s)."
                ),
            }[stop_reason]
            append_message(
                Message(
                    role=Role.SYSTEM,
                    content=(
                        f"{terminal_message} Work and tool results recorded before "
                        "this message still occurred."
                    ),
                )
            )

            measurement = measure(
                self._build_prompt(agent_config, catalog_name),
                self._tools.list_definitions(),
            )
            return AgentLoopResult(
                final_message=response_text,
                turn_messages=Conversation(messages=list(active_turn)),
                stop_reason=stop_reason,
                compression_events=tuple(events),
                context_tokens=measurement.total if measurement else None,
                context_source=measurement.source if measurement else None,
            )

        if catalog_switched_from is not None:
            append_message(
                Message(
                    role=Role.SYSTEM,
                    content=(
                        f"Catalog switched from {catalog_switched_from!r} "
                        f"to {catalog_name!r}."
                    ),
                )
            )

        append_message(Message(role=Role.USER, content=user_text))

        try:
            while turns < agent_config.max_turns:
                if cancel_event.is_set():
                    break

                turns += 1
                streamed_text_parts = []
                streamed_tool_calls = None
                assistant_appended = False

                def capture_chunk(
                    chunk: StreamChunk,
                    text_parts: list[str] = streamed_text_parts,
                ) -> None:
                    nonlocal streamed_tool_calls
                    if chunk.text:
                        text_parts.append(chunk.text)
                    if chunk.done:
                        streamed_tool_calls = chunk.tool_calls
                    if on_chunk is not None:
                        on_chunk(chunk)

                system_prompt = self._build_prompt(agent_config, catalog_name)
                tools = self._tools.list_definitions()
                prepare_turn(system_prompt, tools)

                chat_request = ChatRequest(
                    model=agent_config.model,
                    system_prompt=system_prompt,
                    tools=tools,
                    messages=current_messages(),
                    base_url=agent_config.base_url,
                )

                chat_response = self._complete(
                    provider=agent_config.provider,
                    request=chat_request,
                    stream=stream,
                    on_chunk=capture_chunk,
                    cancel_event=cancel_event,
                )

                response_text = chat_response.content or ""
                tool_calls = chat_response.tool_calls
                append_message(chat_response)
                assistant_appended = True

                if cancel_event.is_set():
                    break

                if not tool_calls:
                    measurement = measure(system_prompt, tools)
                    return AgentLoopResult(
                        final_message=response_text,
                        turn_messages=Conversation(messages=list(active_turn)),
                        stop_reason=StopReason.COMPLETED,
                        compression_events=tuple(events),
                        context_tokens=measurement.total if measurement else None,
                        context_source=measurement.source if measurement else None,
                    )

                tools_output: list[ToolOutput] = self._tools.dispatch(
                    tool_calls,
                    catalog_name=catalog_name,
                    cancel_event=cancel_event,
                )

                # Compress only after every tool result is in, so a summary
                # never contains a half-finished iteration.
                for output in tools_output:
                    append_message(
                        Message(
                            role=Role.TOOL,
                            content=json.dumps(
                                {
                                    "ok": output.ok,
                                    "response": output.response,
                                    "error": output.error,
                                }
                            ),
                            tool_call_id=output.tool_call_id,
                            tool_name=output.tool_name,
                        )
                    )
        except Exception as error:
            if (
                stream
                and not assistant_appended
                and (streamed_text_parts or streamed_tool_calls)
            ):
                response_text = "".join(streamed_text_parts)
                append_message(
                    Message(
                        role=Role.ASSISTANT,
                        content=response_text or None,
                        tool_calls=streamed_tool_calls,
                    )
                )
            result = finish(StopReason.INTERNAL_ERROR)
            raise AgentLoopFailure(result, error) from None

        if cancel_event.is_set():
            return finish(StopReason.CANCELLED)

        return finish(StopReason.MAX_ITERATIONS_EXCEEDED)

    def _complete(
        self,
        provider: str,
        request: ChatRequest,
        stream: bool,
        on_chunk: Callable[[StreamChunk], None] | None,
        cancel_event: threading.Event,
    ) -> Message:
        if not stream:
            return self._router.complete(provider, request)

        return self._consume_stream(
            self._router.stream(provider, request, cancel_event=cancel_event),
            on_chunk=on_chunk,
            cancel_event=cancel_event,
        )

    def _consume_stream(
        self,
        chunks: Iterator[StreamChunk],
        on_chunk: Callable[[StreamChunk], None] | None,
        cancel_event: threading.Event,
    ) -> Message:
        text_parts: list[str] = []
        tool_calls = None
        tokens = None

        for chunk in chunks:
            if cancel_event.is_set():
                break
            if on_chunk is not None:
                on_chunk(chunk)

            if chunk.text:
                text_parts.append(chunk.text)

            if chunk.done:
                tool_calls = chunk.tool_calls
                tokens = chunk.tokens

        return Message(
            role=Role.ASSISTANT,
            content="".join(text_parts) or None,
            tool_calls=tool_calls,
            tokens=tokens,
        )

    def _build_prompt(self, agent_config: AgentConfig, catalog_name: str) -> str:
        return (
            f"{agent_config.system_prompt}\n\n"
            f"Active catalog: {catalog_name!r}. "
            "All tools operate on this catalog. "
            "Do not ask which catalog to use."
        )
