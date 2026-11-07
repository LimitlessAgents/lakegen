from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, replace
from typing import Literal

from lakegen.agent.model import CompressionEvent, CompressionScope, Conversation
from lakegen.inference import ChatRequest, Message, Role, Router
from lakegen.prompt import COMPRESSION_PROMPT
from lakegen.tool.model import ToolDefinition

_COMPRESS_INSTRUCTION = "Now write the compressed summary of the conversation above."
_TURN_SUMMARY_PREFIX = "Summary of earlier activity in this turn:\n\n"
_MIN_TRUNCATED_TOKENS = 512


@dataclass(frozen=True)
class ContextMeasurement:
    """Size of the request we are about to send."""

    total: int
    history: int  # everything except the current turn
    turn: int
    source: Literal["estimated", "anchored"]


@dataclass(frozen=True)
class Compression:
    """Result of one LLM compaction."""

    scope: CompressionScope
    messages: Conversation
    summary: Message
    replaced_messages: int

    @property
    def event(self) -> CompressionEvent:
        return CompressionEvent(
            scope=self.scope,
            summary=self.summary.content or "",
            replaced_messages=self.replaced_messages,
        )


class ContextEngine:
    """Measure, compress and fit the context sent to the model."""

    def measure(
        self,
        *,
        history: Conversation,
        system_prompt: str,
        tools: list[ToolDefinition],
        turn: Conversation | None = None,
    ) -> ContextMeasurement:
        """Estimate the next request size, using the provider's last usage
        report as an anchor when the prefix since then is unchanged."""
        turn = turn if turn is not None else Conversation()
        history_tokens, _ = self._estimate_context(
            history.messages,
            system_prompt,
            tools,
        )
        total, anchored = self._estimate_context(
            [*history.messages, *turn.messages],
            system_prompt,
            tools,
        )
        return ContextMeasurement(
            total=total,
            history=history_tokens,
            turn=self._estimate_messages(turn.messages),
            source="anchored" if anchored else "estimated",
        )

    def _estimate_context(
        self,
        messages: list[Message],
        system_prompt: str,
        tools: list[ToolDefinition],
    ) -> tuple[int, bool]:
        """Estimate one request, anchoring on the newest provider usage report."""
        for index in range(len(messages) - 1, -1, -1):
            usage = messages[index].tokens
            if messages[index].role is Role.ASSISTANT and usage is not None:
                # Usage already includes the system prompt and tool schemas, so
                # only messages added after that response need estimating.
                after = self._estimate_messages(messages[index + 1 :])
                return usage.total_tokens + after, True

        estimated = (
            self._estimate_messages(messages)
            + self._estimate_text(system_prompt)
            + self._estimate_tools(tools)
        )
        return estimated, False

    def compress(
        self,
        scope: CompressionScope,
        conversation: Conversation,
        *,
        router: Router,
        provider: str,
        model: str,
        cancel_event: threading.Event,
        base_url: str | None = None,
    ) -> Compression | None:
        """Replace old messages with one summary, or return ``None`` when
        there is nothing safe to compress."""
        parts = self._parts(scope, conversation.messages)
        if parts is None:
            return None

        leading, target, trailing = parts
        summary = self._summarize(
            target,
            router=router,
            provider=provider,
            model=model,
            cancel_event=cancel_event,
            base_url=base_url,
        )
        if summary is None:
            return None

        if scope is CompressionScope.TURN:
            summary = replace(
                summary,
                content=f"{_TURN_SUMMARY_PREFIX}{summary.content or ''}",
            )

        # Retained messages were built against the uncompressed prefix, so
        # their usage reports are no longer valid anchors.
        leading = [replace(message, tokens=None) for message in leading]
        trailing = [replace(message, tokens=None) for message in trailing]
        messages = [*leading, summary, *trailing]
        return Compression(
            scope=scope,
            messages=Conversation(messages=messages),
            summary=summary,
            replaced_messages=len(target),
        )

    def fit(self, messages: list[Message], *, budget: int) -> Conversation:
        """Deterministically shrink messages until they fit ``budget``.

        Content is truncated (head + tail) before whole completed iterations are
        dropped, so tool-call pairing is never broken. The opening request and
        the newest iteration are never dropped: if they alone exceed the budget,
        the request stays oversized rather than losing the request or breaking
        a pair.
        """
        fitted = list(messages)

        while self._estimate_messages(fitted) > budget:
            index = self._largest_trimmable(fitted)
            if index is None:
                break
            # Halve the largest payload. Targeting the exact excess can stall
            # because the truncation marker adds a little text back.
            keep = max(
                _MIN_TRUNCATED_TOKENS,
                self._estimate_message(fitted[index]) // 2,
            )
            trimmed = self._truncate(fitted[index], keep)
            if trimmed.content == fitted[index].content:
                break
            fitted[index] = trimmed

        while self._estimate_messages(fitted) > budget:
            shortened = self._drop_oldest_iteration(fitted)
            if shortened is None:
                break
            fitted = shortened

        return Conversation(messages=fitted)

    @staticmethod
    def _parts(
        scope: CompressionScope,
        messages: list[Message],
    ) -> tuple[list[Message], list[Message], list[Message]] | None:
        """Split into (leading, summarizable, trailing) without breaking a
        tool-call pair."""
        if scope is CompressionScope.HISTORY:
            return ([], messages, []) if messages else None

        request = next(
            (
                index
                for index, message in enumerate(messages)
                if message.role is Role.USER and not message.is_summary
            ),
            None,
        )
        latest = next(
            (
                index
                for index in range(len(messages) - 1, -1, -1)
                if messages[index].role is Role.ASSISTANT
                and messages[index].tool_calls
            ),
            None,
        )
        if request is None or latest is None or latest <= request + 1:
            # No completed iteration sits between the request and the latest
            # tool call, so there is nothing safe to summarize.
            return None

        # The user request and the in-flight iteration are not summarizable:
        # without them the model cannot continue the turn.
        return messages[: request + 1], messages[request + 1 : latest], messages[latest:]

    def _summarize(
        self,
        messages: list[Message],
        *,
        router: Router,
        provider: str,
        model: str,
        cancel_event: threading.Event,
        base_url: str | None,
    ) -> Message | None:
        request = ChatRequest(
            model=model,
            system_prompt=COMPRESSION_PROMPT,
            messages=[
                *messages,
                Message(role=Role.USER, content=_COMPRESS_INSTRUCTION),
            ],
            tools=[],
            base_url=base_url,
        )

        text_parts: list[str] = []
        for chunk in router.stream(provider, request, cancel_event=cancel_event):
            if cancel_event.is_set():
                return None
            if chunk.text:
                text_parts.append(chunk.text)
        if cancel_event.is_set():
            return None

        content = "".join(text_parts).strip()
        if not content:
            return None

        return Message(role=Role.USER, content=content, is_summary=True)

    def _largest_trimmable(self, messages: list[Message]) -> int | None:
        candidates = [
            (index, message)
            for index, message in enumerate(messages)
            if not message.is_summary
            and message.content
            and (
                message.role in (Role.USER, Role.TOOL)
                or (message.role is Role.ASSISTANT and not message.tool_calls)
            )
        ]
        if not candidates:
            return None

        index, message = max(candidates, key=lambda item: len(item[1].content or ""))
        if self._estimate_message(message) <= _MIN_TRUNCATED_TOKENS * 2:
            return None
        return index

    @staticmethod
    def _truncate(message: Message, keep_tokens: int) -> Message:
        text = message.content or ""
        keep_chars = max(0, keep_tokens * 4)
        if len(text) <= keep_chars:
            return message

        side = keep_chars // 2
        omitted = (len(text) - keep_chars + 3) // 4
        content = (
            f"{text[:side]}\n\n"
            f"[truncated {omitted:,} tokens; full content is stored in turn history]\n\n"
            f"{text[-side:]}"
        )
        # The old usage report describes the untruncated request.
        return replace(message, content=content, tokens=None)

    @staticmethod
    def _drop_oldest_iteration(messages: list[Message]) -> list[Message] | None:
        latest = next(
            (
                index
                for index in range(len(messages) - 1, -1, -1)
                if messages[index].role is Role.ASSISTANT
                and messages[index].tool_calls
            ),
            None,
        )
        first = next(
            (
                index
                for index, message in enumerate(messages)
                if message.role is Role.ASSISTANT and message.tool_calls
            ),
            None,
        )
        if latest is None or first is None or first >= latest:
            return None

        end = first + 1
        while end < latest and messages[end].role is Role.TOOL:
            end += 1
        return [*messages[:first], *messages[end:]]

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
