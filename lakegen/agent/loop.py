import json
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
    router as inference_router,
)
from lakegen.tool.model import ToolOutput
from lakegen.tool.runtime import runtime as tool_runtime


class AgentLoop:
    def invoke(
        self,
        agent_config: AgentConfig,
        conversation: Conversation,
        user_text: str,
        stream: bool = False,
        on_chunk: Callable[[StreamChunk], None] | None = None,
    ) -> AgentLoopResult:
        conversation.messages.append(Message(role=Role.USER, content=user_text))

        turns = 0
        response_text = ""

        while turns < agent_config.max_turns:
            turns += 1

            chat_request = ChatRequest(
                model=agent_config.model,
                system_prompt=agent_config.system_prompt,
                tools=agent_config.tools,
                messages=conversation.messages,
            )

            chat_response = self._complete(
                provider=agent_config.provider,
                request=chat_request,
                stream=stream,
                on_chunk=on_chunk,
            )

            response_text = chat_response.message.content or ""
            tool_calls = chat_response.message.tool_calls

            conversation.messages.append(chat_response.message)

            if not tool_calls:
                return AgentLoopResult(
                    final_message=response_text,
                    transcript=conversation,
                    stop_reason=StopReason.COMPLETED,
                )

            tools_output: list[ToolOutput] = tool_runtime.dispatch(tool_calls)

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
    ) -> ChatResponse:
        if not stream:
            return inference_router.complete(provider, request)

        return self._consume_stream(
            inference_router.stream(provider, request),
            on_chunk=on_chunk,
        )

    def _consume_stream(
        self,
        chunks: Iterator[StreamChunk],
        on_chunk: Callable[[StreamChunk], None] | None,
    ) -> ChatResponse:
        text_parts: list[str] = []
        tool_calls = None
        tokens = None

        for chunk in chunks:
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
