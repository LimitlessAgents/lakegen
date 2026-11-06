import json
import threading
from dataclasses import asdict, replace

from lakegen.agent.model import Conversation
from lakegen.inference import ChatRequest, Message, Role, Router
from lakegen.prompt import COMPRESSION_PROMPT
from lakegen.tool.model import ToolDefinition

# Keep the most recent user turns verbatim, bounded by this share of the
# conversation budget. Everything older is replaced by the summary. Both
# compression and hydration use :meth:`ContextEngine.tail` so the window is
# defined in exactly one place.
TAIL_TURNS = 3
TAIL_TOKEN_RATIO = 0.15

# TODO(tool-output-cap): cap tool output before it enters the model context.
# Deferred: Not implemented because the roadmap includes visualisations,
# deterministic algorithms designed to take the load off the llm
# which might need the results verbatim.
# Truncating at retrieval time would break that.
# This needs more thought and design decisions.

COMPRESSION_THRESHOLD = 0.6
_COMPRESS_INSTRUCTION = "Now write the compressed summary of the conversation above."

# TODO(compression-input-budget): compression sends the whole conversation in
# one request. A single oversized user message or tool output can leave too
# little room in the compression model's context window for a summary. If the
# compression request itself does not fit, compression fails and the turn
# proceeds uncompressed. Needs a strategy (chunked/rolling summary, explicit
# input truncation, or a pre-invoke guard) that uses the compression model's
# context limit, which may be smaller than the session model's.

# TODO(current-turn-over-budget): the newest user turn is kept verbatim even
# when it alone exceeds the tail budget. If summary + that turn stays at or
# above the compression threshold, every following gate compresses again; a
# single-turn conversation skips compression entirely because tail_start == 0.
# Needs an in-memory-only strategy (tail/tool-output truncation, pruning, or
# chunked compression) instead of repeated summarization.


class ContextEngine:
    """Stateless context sizing and compression."""

    def estimate_context_tokens(
        self,
        conversation: Conversation,
        *,
        system_prompt: str,
        tools: list[ToolDefinition],
    ) -> int:
        messages = conversation.messages
        overhead = self._estimate_text(system_prompt) + self._estimate_tools(tools)

        for index in range(len(messages) - 1, -1, -1):
            message = messages[index]
            if message.is_summary:
                base = (
                    message.tokens.completion_tokens
                    if message.tokens is not None
                    else self._estimate_message(message)
                )
                return base + self._estimate_messages(messages[index + 1 :]) + overhead
            if message.role is Role.ASSISTANT and message.tokens is not None:
                # total_tokens already includes system prompt and tool definitions.
                return message.tokens.total_tokens + self._estimate_messages(
                    messages[index + 1 :]
                )

        return self._estimate_messages(messages) + overhead

    def needs_compression(
        self,
        conversation: Conversation,
        *,
        budget_tokens: int,
        system_prompt: str,
        tools: list[ToolDefinition],
    ) -> bool:
        if budget_tokens <= 0:
            return False
        size = self.estimate_context_tokens(
            conversation,
            system_prompt=system_prompt,
            tools=tools,
        )
        return size >= budget_tokens * COMPRESSION_THRESHOLD

    def compress(
        self,
        conversation: Conversation,
        *,
        budget_tokens: int,
        router: Router,
        provider: str,
        model: str,
        cancel_event: threading.Event,
        base_url: str | None = None,
    ) -> Conversation:
        messages = conversation.messages
        tail_start = self._tail_start(messages, budget_tokens)
        if tail_start == 0:
            return conversation

        request = ChatRequest(
            model=model,
            system_prompt=COMPRESSION_PROMPT,
            messages=[
                *conversation.messages,
                Message(role=Role.USER, content=_COMPRESS_INSTRUCTION),
            ],
            tools=[],
            base_url=base_url,
        )

        text_parts: list[str] = []
        last_chunk = None
        for chunk in router.stream(provider, request, cancel_event=cancel_event):
            last_chunk = chunk
            if cancel_event.is_set():
                return conversation
            if chunk.text:
                text_parts.append(chunk.text)
        if cancel_event.is_set():
            return conversation

        content = "".join(text_parts)
        if not content.strip():
            return conversation

        summary = Message(
            role=Role.USER,
            content=content,
            tokens=last_chunk.tokens if last_chunk is not None else None,
            is_summary=True,
        )

        tail = self.tail(messages, budget_tokens=budget_tokens)
        return Conversation(messages=[summary, *tail])

    def tail(
        self,
        messages: list[Message],
        *,
        budget_tokens: int,
    ) -> list[Message]:
        """Return the newest turns that are kept verbatim after a summary.

        The window always starts at the most recent user turn, so an
        in-flight turn survives compression.

        Used both right after compression and when hydration has no turns
        stored after the summary marker, so a tail is rebuilt instead of
        persisted.
        """
        start = self._tail_start(messages, budget_tokens)
        return [
            replace(message, is_tail=True) for message in messages[start:]
        ]

    def _tail_start(self, messages: list[Message], budget_tokens: int) -> int:
        user_starts = [
            index
            for index, message in enumerate(messages)
            if message.role is Role.USER and not message.is_summary
        ]
        if not user_starts:
            return len(messages)

        cap = budget_tokens * TAIL_TOKEN_RATIO
        # Always keep the most recent user turn: dropping it would leave the
        # model without the request it is answering. Older turns are included
        # again only while the window stays inside the token cap.
        tail_start = user_starts[-1]
        for index in reversed(user_starts[-TAIL_TURNS:-1]):
            if self._estimate_messages(messages[index:]) <= cap:
                tail_start = index
            else:
                break
        return tail_start

    def _estimate_messages(self, messages: list[Message]) -> int:
        return sum(self._estimate_message(message) for message in messages)

    def _estimate_message(self, message: Message) -> int:
        parts = [
            message.content or "",
            message.tool_call_id or "",
            message.tool_name or "",
        ]
        if message.tool_calls:
            parts.append(json.dumps([asdict(call) for call in message.tool_calls]))
        return self._estimate_text("".join(parts))

    def _estimate_tools(self, tools: list[ToolDefinition]) -> int:
        if not tools:
            return 0
        return self._estimate_text(json.dumps([tool.to_dict() for tool in tools]))

    @staticmethod
    def _estimate_text(text: str) -> int:
        return (len(text) + 3) // 4
