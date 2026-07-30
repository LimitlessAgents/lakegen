import json

from lakegen.agent.model import (
    AgentConfig,
    Conversation,
    AgentLoopResult,
    StopReason
)

from lakegen.inference import (
    ChatRequest,
    ChatResponse,
    Message,
    Role,
    router as inference_router,
)
from lakegen.tool.model import ToolOutput
from lakegen.tool.runtime import runtime as tool_runtime


class AgentLoop:
    def invoke(
        self,
        agent_config: AgentConfig,
        user_text: str,
        conversation: Conversation
    ) -> AgentLoopResult:
        user_message = Message(role=Role.USER, content=user_text)
        conversation.messages.append(user_message)

        turns = 0

        while turns < agent_config.max_turns:

            turns += 1

            chat_request: ChatRequest = ChatRequest(
                model=agent_config.model,
                system_prompt=agent_config.system_prompt,
                tools=agent_config.tools,
                messages=conversation.messages,
            )

            chat_response: ChatResponse = inference_router.complete("openai", chat_request)

            response_text = chat_response.message.content
            tool_calls = chat_response.message.tool_calls or None

            conversation.messages.append(chat_response.message)

            if not tool_calls:
                return AgentLoopResult(
                    final_message=response_text,
                    transcript=conversation,
                    stop_reason=StopReason.COMPLETED
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
                                "error": output.error
                            }
                        ),
                        tool_call_id=output.tool_call_id,
                        tool_name=output.tool_name,
                    )
                )

        return AgentLoopResult(
            final_message=response_text,
            transcript=conversation,
            stop_reason=StopReason.MAX_ITERATIONS_EXCEEDED
        )