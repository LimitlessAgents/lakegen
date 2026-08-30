import json
import threading
from collections.abc import Callable, Iterator

from lakegen.agent.model import (
    AgentConfig,
    AgentLoopFailure,
    Conversation,
    AgentLoopResult,
    StopReason,
)
from lakegen.inference import (
    ChatRequest,
    ChatResponse,
    Message,
    Role,
    StreamChunk,
    Router,
    router as default_router,
)
from lakegen.tool.model import ToolOutput
from lakegen.tool.runtime import ToolRuntime, runtime as default_tool_runtime


class AgentLoop:
    def __init__(
        self,
        router: Router | None = None,
        tool_runtime: ToolRuntime | None = None,
    ) -> None:
        self._router = router if router is not None else default_router
        self._tools = tool_runtime if tool_runtime is not None else default_tool_runtime

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
    ) -> AgentLoopResult:
        turn_messages = Conversation()
        turns = 0
        response_text = ""
        streamed_text_parts: list[str] = []
        streamed_tool_calls = None
        assistant_appended = True

        def append_message(message: Message) -> None:
            turn_messages.messages.append(message)

        def current_messages() -> list[Message]:
            return conversation.messages + turn_messages.messages

        def finish(stop_reason: StopReason) -> AgentLoopResult:
            resolved_call_ids = {
                message.tool_call_id
                for message in turn_messages.messages
                if message.role is Role.TOOL and message.tool_call_id is not None
            }
            for message in tuple(turn_messages.messages):
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
            return AgentLoopResult(
                final_message=response_text,
                turn_messages=turn_messages,
                stop_reason=stop_reason,
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

        system_prompt = (
            f"{agent_config.system_prompt}\n\n"
            f"Active catalog: {catalog_name!r}. "
            "All tools operate on this catalog. "
            "Do not ask which catalog to use."
        )

        try:
            while turns < agent_config.max_turns:
                if cancel_event.is_set():
                    break

                turns += 1
                streamed_text_parts = []
                streamed_tool_calls = None
                assistant_appended = False

                def capture_chunk(chunk: StreamChunk) -> None:
                    nonlocal streamed_tool_calls
                    if chunk.text:
                        streamed_text_parts.append(chunk.text)
                    if chunk.done:
                        streamed_tool_calls = chunk.tool_calls
                    if on_chunk is not None:
                        on_chunk(chunk)

                chat_request = ChatRequest(
                    model=agent_config.model,
                    system_prompt=system_prompt,
                    tools=self._tools.list_definitions(),
                    messages=current_messages(),
                )

                chat_response = self._complete(
                    provider=agent_config.provider,
                    request=chat_request,
                    stream=stream,
                    on_chunk=capture_chunk,
                    cancel_event=cancel_event,
                )

                response_text = chat_response.message.content or ""
                tool_calls = chat_response.message.tool_calls
                append_message(chat_response.message)
                assistant_appended = True

                if cancel_event.is_set():
                    break

                if not tool_calls:
                    return AgentLoopResult(
                        final_message=response_text,
                        turn_messages=turn_messages,
                        stop_reason=StopReason.COMPLETED,
                    )

                tools_output: list[ToolOutput] = self._tools.dispatch(
                    tool_calls,
                    catalog_name=catalog_name,
                    cancel_event=cancel_event,
                )

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
            if stream and not assistant_appended and (
                streamed_text_parts or streamed_tool_calls
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
    ) -> ChatResponse:
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
    ) -> ChatResponse:
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

        return ChatResponse(
            message=Message(
                role=Role.ASSISTANT,
                content="".join(text_parts) or None,
                tool_calls=tool_calls,
            ),
            tokens=tokens,
        )
