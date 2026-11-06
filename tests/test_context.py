import threading
from unittest.mock import MagicMock

from lakegen.agent.model import Conversation
from lakegen.inference import Message, Role, StreamChunk, TokenUsage
from lakegen.session.context import ContextEngine


def _assistant(content: str, total: int) -> Message:
    return Message(
        role=Role.ASSISTANT,
        content=content,
        tokens=TokenUsage(total, 10, total),
    )


def _summary(content: str = "summary") -> Message:
    return Message(
        role=Role.USER,
        content=content,
        is_summary=True,
        tokens=TokenUsage(100, 50, 150),
    )


def test_last_assistant_total_tokens_is_context_size() -> None:
    engine = ContextEngine()
    conversation = Conversation(
        messages=[
            Message(role=Role.USER, content="hi"),
            _assistant("hello", 500),
        ]
    )

    assert (
        engine.estimate_context_tokens(
            conversation,
            system_prompt="system",
            tools=[],
        )
        == 500
    )


def test_messages_after_last_assistant_are_estimated() -> None:
    engine = ContextEngine()
    tail = Message(role=Role.TOOL, content="x" * 40, tool_call_id="1")
    conversation = Conversation(
        messages=[
            Message(role=Role.USER, content="hi"),
            _assistant("hello", 500),
            tail,
        ]
    )

    assert engine.estimate_context_tokens(
        conversation,
        system_prompt="system",
        tools=[],
    ) == 500 + engine._estimate_message(tail)


def test_summary_uses_completion_tokens_plus_tail_and_overhead() -> None:
    engine = ContextEngine()
    tail = Message(role=Role.TOOL, content="x" * 40, tool_call_id="1")
    conversation = Conversation(messages=[_summary(), tail])

    expected = 50 + engine._estimate_message(tail) + engine._estimate_text("system")
    assert (
        engine.estimate_context_tokens(
            conversation,
            system_prompt="system",
            tools=[],
        )
        == expected
    )


def test_needs_compression_uses_budget_threshold() -> None:
    engine = ContextEngine()
    conversation = Conversation(
        messages=[Message(role=Role.ASSISTANT, content="x" * 400)]
    )

    assert engine.needs_compression(
        conversation,
        budget_tokens=100,
        system_prompt="",
        tools=[],
    )
    assert not engine.needs_compression(
        conversation,
        budget_tokens=1_000,
        system_prompt="",
        tools=[],
    )


def test_compress_keeps_recent_user_turns_and_marks_them_as_tail() -> None:
    engine = ContextEngine()
    router = MagicMock()
    router.stream.return_value = [
        StreamChunk(text="summary", done=True, tokens=TokenUsage(100, 50, 150))
    ]

    messages = [
        Message(role=Role.USER, content="old"),
        _assistant("old answer" + "x" * 4_000, 300),
        Message(role=Role.USER, content="recent"),
        _assistant("recent answer", 400),
    ]

    compressed = engine.compress(
        Conversation(messages=messages),
        budget_tokens=4_000,
        router=router,
        provider="fake",
        model="model",
        cancel_event=threading.Event(),
    )

    assert compressed.messages[0].is_summary is True
    assert compressed.messages[0].content == "summary"
    assert [m.content for m in compressed.messages[1:]] == [
        "recent",
        "recent answer",
    ]
    assert all(m.is_tail for m in compressed.messages[1:])
    # Tail messages are kept verbatim; the summary flag is the marker.
    assert [m.tokens for m in compressed.messages[1:]] == [
        messages[2].tokens,
        messages[3].tokens,
    ]


def test_tail_always_includes_the_latest_turn() -> None:
    engine = ContextEngine()
    messages = [
        Message(role=Role.USER, content="huge"),
        Message(role=Role.ASSISTANT, content="x" * 40_000),
    ]

    tail = engine.tail(messages, budget_tokens=100)

    assert [m.content for m in tail] == ["huge", "x" * 40_000]
    assert all(m.is_tail for m in tail)


