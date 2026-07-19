import json
from typing import Any

from lakegen.inference.model import (
    ChatRequest,
    ChatResponse,
    Message,
    Role,
    TokenUsage,
    ToolCall,
    ToolDefinition,
)
from lakegen.inference.protocol import ProviderCapabilities
from lakegen.inference.registry import registry


class _OpenAI:
    """OpenAI Responses API adapter."""

    def __init__(self) -> None:
        self.client = None

    @property
    def name(self) -> str:
        return "openai"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            chat=True,
            tools=True,
            streaming=False,
            json_schema=True,
        )

    def _get_client(self):
        # Build once, reuse.
        if not self.client:
            from openai import OpenAI
            self.client = OpenAI()
        return self.client

    def _tools_to_native(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        # lakegen ToolDefinition → OpenAI function tools.
        return [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.arguments,
            }
            for tool in tools
        ]

    def _message_to_native(self, messages: list[Message]) -> list[dict[str, Any]]:
        # Canonical messages → Responses API input items.
        native: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == Role.TOOL:
                # Tool runtime result for a prior call.
                output = msg.content
                if not isinstance(output, str):
                    output = json.dumps(output)
                native.append(
                    {
                        "type": "function_call_output",
                        "call_id": msg.tool_call_id,
                        "output": output,
                    }
                )
                continue

            if msg.role == Role.ASSISTANT and msg.tool_calls:
                # Prior assistant turn that requested tools.
                if msg.content:
                    native.append({"role": "assistant", "content": msg.content})
                for call in msg.tool_calls:
                    native.append(
                        {
                            "type": "function_call",
                            "call_id": call.id,
                            "name": call.name,
                            "arguments": json.dumps(call.arguments),
                        }
                    )
                continue

            # Normal user / assistant / system text turn.
            native.append(
                {
                    "role": msg.role.value,
                    "content": msg.content,
                }
            )
        return native

    def complete(self, request: ChatRequest) -> ChatResponse:
        client = self._get_client()
        tools = self._tools_to_native(request.tools) or None

        response = client.responses.create(
            model=request.model,
            instructions=request.system_prompt,
            tools=tools,
            input=self._message_to_native(request.messages),
            temperature=request.temperature,
        )

        # Pull tool calls out of the response output list.
        tool_calls: list[ToolCall] = []
        for item in response.output:
            if item.type == "function_call":
                args = item.arguments
                if isinstance(args, str):
                    args = json.loads(args)
                tool_calls.append(ToolCall(item.call_id, item.name, args))

        tokens = None
        if response.usage is not None:
            tokens = TokenUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.total_tokens,
            )

        return ChatResponse(
            message=Message(
                role=Role.ASSISTANT,
                content=response.output_text or None,
                tool_calls=tool_calls or None,
            ),
            tokens=tokens,
        )

    def stream(self, request: ChatRequest):
        raise NotImplementedError("streaming not implemented yet")


registry.register(_OpenAI())
