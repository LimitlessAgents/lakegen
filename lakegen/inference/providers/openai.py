import json
from typing import Any, Iterator

import openai

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.inference.model import (
    ChatRequest,
    ChatResponse,
    Message,
    Role,
    StreamChunk,
    TokenUsage,
    ToolCall,
    ToolDefinition,
)
from lakegen.inference.protocol import ProviderCapabilities
from lakegen.inference.registry import registry


class _OpenAI:
    """OpenAI Responses API adapter.

    Enforces inactivity timeouts on each SDK call, disables SDK-native retries
    (the Router owns retry policy), and maps vendor errors into ``BaseError``.
    """

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
            streaming=True,
            json_schema=True,
        )

    def _get_client(self):
        """Lazily build a shared OpenAI client with SDK retries disabled."""
        if self.client is None:
            from openai import OpenAI

            # max_retries=0 avoids nested retries under the Router's policy.
            self.client = OpenAI(max_retries=0)
        return self.client

    def _parse_retry_after(self, error: Exception) -> float | None:
        """Read numeric ``Retry-After`` seconds from an API status error, if present."""
        if not isinstance(error, openai.APIStatusError):
            return None
        header = error.response.headers.get("retry-after")
        if header is None:
            return None
        try:
            value = float(header)
        except (TypeError, ValueError):
            return None
        if value < 0:
            return None
        return value

    def _map_error(self, error: Exception, model: str) -> BaseError:
        """Translate an OpenAI SDK exception into a structured BaseError.

        Details include provider, model, HTTP status, request id, and numeric
        ``retry_after`` seconds when the response provides ``Retry-After``.
        Response bodies and credentials are never attached.
        """
        status = (
            error.status_code
            if isinstance(error, openai.APIStatusError)
            else None
        )
        request_id = (
            error.request_id
            if isinstance(error, openai.APIStatusError)
            else None
        )
        details: dict[str, Any] = {
            "provider": self.name,
            "model": model,
        }
        if status is not None:
            details["status"] = status
        if request_id is not None:
            details["request_id"] = request_id

        # Seconds form only; HTTP-date Retry-After values are ignored.
        retry_after = self._parse_retry_after(error)
        if retry_after is not None:
            details["retry_after"] = retry_after

        if (
            isinstance(error, openai.NotFoundError)
            or getattr(error, "code", None) == "model_not_found"
        ):
            return BaseError(
                ErrorCode.MODEL_NOT_FOUND,
                f"OpenAI model {model!r} was not found.",
                is_retryable=False,
                is_user_fixable=True,
                details=details,
            )

        if isinstance(error, openai.RateLimitError) or status == 429:
            return BaseError(
                ErrorCode.RATE_LIMITED,
                "OpenAI rate limit exceeded.",
                is_retryable=True,
                is_user_fixable=False,
                details=details,
            )

        if (
            isinstance(
                error,
                (openai.APITimeoutError, openai.APIConnectionError),
            )
            or status in {408, 409}
            or (status is not None and status >= 500)
        ):
            return BaseError(
                ErrorCode.INFERENCE_FAILED,
                "OpenAI is temporarily unavailable.",
                is_retryable=True,
                is_user_fixable=False,
                details=details,
            )

        # Deterministic client / config problems (4xx, auth) vs unclassified.
        is_client_error = (
            status is not None and 400 <= status < 500
        ) or (
            isinstance(error, openai.OpenAIError)
            and not isinstance(error, openai.APIError)
        )
        return BaseError(
            ErrorCode.INFERENCE_FAILED,
            "OpenAI inference failed.",
            is_retryable=False,
            is_user_fixable=is_client_error,
            details=details,
        )

    def _tools_to_native(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Convert lakegen tool definitions to OpenAI function tools."""
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
        """Convert canonical messages to Responses API input items."""
        native: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == Role.TOOL:
                # Tool runtime result for a prior function_call.
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

    def complete(
        self,
        request: ChatRequest,
        *,
        inactivity_timeout: float,
    ) -> ChatResponse:
        """Run a non-streaming Responses API call and normalize the result."""
        try:
            response = self._get_client().responses.create(
                model=request.model,
                instructions=request.system_prompt,
                tools=self._tools_to_native(request.tools) or None,
                input=self._message_to_native(request.messages),
                temperature=request.temperature,
                timeout=inactivity_timeout,
            )

            # Responses API returns a list of output items (text, tool calls, …).
            tool_calls: list[ToolCall] = []
            for item in response.output:
                if item.type == "function_call":
                    args = item.arguments
                    if isinstance(args, str):
                        args = json.loads(args)
                    tool_calls.append(ToolCall(item.call_id, item.name, args))

            tokens = (
                TokenUsage(
                    prompt_tokens=response.usage.input_tokens,
                    completion_tokens=response.usage.output_tokens,
                    total_tokens=response.usage.total_tokens,
                )
                if response.usage
                else None
            )

            return ChatResponse(
                message=Message(
                    role=Role.ASSISTANT,
                    content=response.output_text or None,
                    tool_calls=tool_calls or None,
                ),
                tokens=tokens,
            )
        except BaseError:
            raise
        except Exception as error:
            raise self._map_error(error, request.model) from error

    def stream(
        self,
        request: ChatRequest,
        *,
        inactivity_timeout: float,
    ) -> Iterator[StreamChunk]:
        """Stream Responses API events into lakegen ``StreamChunk`` values.

        Text arrives as deltas. Tool calls arrive as finished output items
        and are held until ``response.completed``, then emitted on the final
        chunk with ``done=True``.
        """
        try:
            stream = self._get_client().responses.create(
                model=request.model,
                instructions=request.system_prompt,
                tools=self._tools_to_native(request.tools) or None,
                input=self._message_to_native(request.messages),
                temperature=request.temperature,
                stream=True,
                timeout=inactivity_timeout,
            )

            tool_calls: list[ToolCall] = []

            for event in stream:
                if event.type == "response.output_text.delta":
                    yield StreamChunk(text=event.delta)

                elif event.type == "response.output_item.done":
                    # One output item finished; collect completed tool calls.
                    item = event.item
                    if item.type == "function_call":
                        args = (
                            json.loads(item.arguments)
                            if isinstance(item.arguments, str)
                            else item.arguments
                        )
                        tool_calls.append(
                            ToolCall(item.call_id, item.name, args)
                        )

                elif event.type == "response.completed":
                    usage = event.response.usage
                    tokens = (
                        TokenUsage(
                            prompt_tokens=usage.input_tokens,
                            completion_tokens=usage.output_tokens,
                            total_tokens=usage.total_tokens,
                        )
                        if usage
                        else None
                    )

                    yield StreamChunk(
                        done=True,
                        tool_calls=tool_calls or None,
                        tokens=tokens,
                    )
        except BaseError:
            raise
        except Exception as error:
            raise self._map_error(error, request.model) from error


registry.register(_OpenAI())
