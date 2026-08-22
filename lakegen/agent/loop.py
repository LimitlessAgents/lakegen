import json
import threading
from collections.abc import Callable, Iterator

from lakegen.agent.model import (
    AgentConfig,
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
        if catalog_switched_from is not None:
            conversation.messages.append(
                Message(
                    role=Role.SYSTEM,
                    content=(
                        f"Catalog switched from {catalog_switched_from!r} "
                        f"to {catalog_name!r}."
                    ),
                )
            )

        conversation.messages.append(Message(role=Role.USER, content=user_text))

        system_prompt = (
            f"{agent_config.system_prompt}\n\n"
            f"Active catalog: {catalog_name!r}. "
            "All tools operate on this catalog. "
            "Do not ask which catalog to use."
        )

        turns = 0
        response_text = ""

        while turns < agent_config.max_turns:
            if cancel_event.is_set():
                break

            turns += 1

            chat_request = ChatRequest(
                model=agent_config.model,
                system_prompt=system_prompt,
                tools=self._tools.list_definitions(),
                messages=conversation.messages,
            )

            chat_response = self._complete(
                provider=agent_config.provider,
                request=chat_request,
                stream=stream,
                on_chunk=on_chunk,
                cancel_event=cancel_event,
            )

            if cancel_event.is_set():
                break

            response_text = chat_response.message.content or ""
            tool_calls = chat_response.message.tool_calls

            conversation.messages.append(chat_response.message)

            if not tool_calls:
                return AgentLoopResult(
                    final_message=response_text,
                    transcript=conversation,
                    stop_reason=StopReason.COMPLETED,
                )

            if cancel_event.is_set():
                break

            tools_output: list[ToolOutput] = self._tools.dispatch(
                tool_calls,
                catalog_name=catalog_name,
                cancel_event=cancel_event,
            )

            for output in tools_output:
                conversation.messages.append(
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

        # TODO(cancel): Roll back conversation to the pre-invoke checkpoint;
        # cancel exits without reverting mutations today.
        if cancel_event.is_set():
            return AgentLoopResult(
                final_message=response_text,
                transcript=conversation,
                stop_reason=StopReason.CANCELLED,
            )

        return AgentLoopResult(
            final_message=response_text,
            transcript=conversation,
            stop_reason=StopReason.MAX_ITERATIONS_EXCEEDED,
        )

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
