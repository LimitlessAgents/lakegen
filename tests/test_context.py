import threading
from unittest.mock import MagicMock

from lakegen.agent.model import CompressionScope, Conversation
from lakegen.inference import Message, Role, StreamChunk, TokenUsage
from lakegen.session.context import ContextEngine
from lakegen.agent.policy import ContextPolicy, TurnCompressionState
from lakegen.tool.model import ToolCall


def _assistant(content=None, *, tool_calls=None, total=None) -> Message:
    return Message(
        role=Role.ASSISTANT,
        content=content,
        tool_calls=tool_calls,
        tokens=TokenUsage(total, 10, total) if total is not None else None,
    )


def _tool(call_id: str, content: str) -> Message:
    return Message(
        role=Role.TOOL,
        content=content,
        tool_call_id=call_id,
        tool_name="run_query",
    )


def _stream(router: MagicMock, text: str) -> None:
    def fake_stream(provider, request, *, cancel_event):
        yield StreamChunk(text=text, done=True, tokens=TokenUsage(100, 20, 120))

    router.stream.side_effect = fake_stream


def test_measure_uses_last_assistant_usage_as_an_anchor() -> None:
    engine = ContextEngine()
    conversation = Conversation(
        messages=[
            Message(role=Role.USER, content="hi"),
            _assistant("hello", total=500),
        ]
    )

    measurement = engine.measure(
        history=conversation,
        system_prompt="system",
        tools=[],
    )

    assert measurement.total == 500
    assert measurement.history == 500
    assert measurement.turn == 0
    assert measurement.source == "anchored"


def test_measure_estimates_when_there_is_no_anchor() -> None:
    engine = ContextEngine()
    conversation = Conversation(
        messages=[Message(role=Role.USER, content="x" * 400)]
    )

    measurement = engine.measure(
        history=conversation,
        system_prompt="system",
        tools=[],
    )

    assert measurement.total == engine._estimate_messages(conversation.messages) + 2
    assert measurement.source == "estimated"


def test_measure_splits_history_from_the_current_turn() -> None:
    engine = ContextEngine()
    history = Conversation(
        messages=[
            Message(role=Role.USER, content="hi"),
            _assistant("hello", total=500),
        ]
    )
    turn = Conversation(messages=[Message(role=Role.USER, content="x" * 400)])
    turn_tokens = engine._estimate_messages(turn.messages)

    measurement = engine.measure(
        history=history,
        turn=turn,
        system_prompt="system",
        tools=[],
    )

    assert measurement.turn == turn_tokens
    assert measurement.history == 500
    assert measurement.total == 500 + turn_tokens


def test_history_compression_replaces_all_history_with_the_summary() -> None:
    router = MagicMock()
    _stream(router, "summary")
    conversation = Conversation(
        messages=[
            Message(role=Role.USER, content="old question"),
            _assistant("old answer", total=900),
        ]
    )

    compression = ContextEngine().compress(
        CompressionScope.HISTORY,
        conversation,
        router=router,
        provider="openai",
        model="gpt-4o",
        cancel_event=threading.Event(),
    )

    assert compression is not None
    assert compression.replaced_messages == 2
    assert [message.content for message in compression.messages.messages] == ["summary"]
    assert compression.messages.messages[0].is_summary is True

    request = router.stream.call_args.args[1]
    assert [message.content for message in request.messages[:-1]] == [
        "old question",
        "old answer",
    ]
    assert request.messages[-1].content == (
        "Now write the compressed summary of the conversation above."
    )


def test_turn_compression_keeps_the_request_and_latest_iteration() -> None:
    router = MagicMock()
    _stream(router, "condensed")
    call = ToolCall("call-1", "run_query", {"sql": "select 1"})
    latest = ToolCall("call-2", "run_query", {"sql": "select 2"})
    conversation = Conversation(
        messages=[
            Message(role=Role.USER, content="question"),
            _assistant(tool_calls=[call], total=400),
            _tool("call-1", '{"rows": 1}'),
            _assistant(tool_calls=[latest], total=500),
            _tool("call-2", '{"rows": 2}'),
        ]
    )

    compression = ContextEngine().compress(
        CompressionScope.TURN,
        conversation,
        router=router,
        provider="openai",
        model="gpt-4o",
        cancel_event=threading.Event(),
    )

    assert compression is not None
    assert compression.replaced_messages == 2
    messages = compression.messages.messages
    assert [message.role for message in messages] == [
        Role.USER,
        Role.USER,
        Role.ASSISTANT,
        Role.TOOL,
    ]
    assert messages[0].content == "question"
    assert messages[1].is_summary is True
    assert messages[1].content.startswith("Summary of earlier activity in this turn:")
    assert messages[2].tool_calls == [latest]
    # Retained messages were produced against the uncompressed prefix, so
    # their token usage must not be reused as an anchor.
    assert messages[2].tokens is None


def test_turn_compression_skips_a_single_iteration() -> None:
    call = ToolCall("call-1", "run_query", {})
    conversation = Conversation(
        messages=[
            Message(role=Role.USER, content="question"),
            _assistant(tool_calls=[call]),
            _tool("call-1", "{}"),
        ]
    )

    assert (
        ContextEngine().compress(
            CompressionScope.TURN,
            conversation,
            router=MagicMock(),
            provider="openai",
            model="gpt-4o",
            cancel_event=threading.Event(),
        )
        is None
    )


def test_compression_aborts_on_cancel() -> None:
    router = MagicMock()
    cancel_event = threading.Event()

    def fake_stream(provider, request, *, cancel_event):
        yield StreamChunk(text="partial")
        cancel_event.set()
        yield StreamChunk(text="ignored")

    router.stream.side_effect = fake_stream

    assert (
        ContextEngine().compress(
            CompressionScope.HISTORY,
            Conversation(messages=[Message(role=Role.USER, content="hello")]),
            router=router,
            provider="openai",
            model="gpt-4o",
            cancel_event=cancel_event,
        )
        is None
    )


def test_fit_truncates_the_largest_payload_and_preserves_pairing() -> None:
    engine = ContextEngine()
    call = ToolCall("call-1", "run_query", {"sql": "select 1"})
    messages = [
        Message(role=Role.USER, content="question"),
        _assistant(tool_calls=[call]),
        _tool("call-1", "x" * 40_000),
    ]

    fitted = engine.fit(messages, budget=1_000)

    tool_message = fitted.messages[-1]
    assert tool_message.tool_call_id == "call-1"
    assert tool_message.tool_name == "run_query"
    assert "truncated" in (tool_message.content or "")
    assert engine._estimate_messages(fitted.messages) <= 1_000


def test_fit_drops_old_iterations_before_the_latest_one() -> None:
    engine = ContextEngine()
    first = ToolCall("call-1", "run_query", {"sql": "x" * 20_000})
    latest = ToolCall("call-2", "run_query", {"sql": "y" * 20_000})
    messages = [
        Message(role=Role.USER, content="question"),
        _assistant(tool_calls=[first]),
        _tool("call-1", "{}"),
        _assistant(tool_calls=[latest]),
        _tool("call-2", "{}"),
    ]

    fitted = engine.fit(messages, budget=1)

    roles = [message.role for message in fitted.messages]
    assert roles == [Role.USER, Role.ASSISTANT, Role.TOOL]
    assert fitted.messages[1].tool_calls == [latest]


def test_compress_forwards_the_session_endpoint() -> None:
    router = MagicMock()
    _stream(router, "summary")

    ContextEngine().compress(
        CompressionScope.HISTORY,
        Conversation(messages=[Message(role=Role.USER, content="hello")]),
        router=router,
        provider="openai",
        model="gpt-4o",
        cancel_event=threading.Event(),
        base_url="https://openrouter.ai/api/v1",
    )

    assert router.stream.call_args.args[1].base_url == "https://openrouter.ai/api/v1"


def test_policy_reads_the_window_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("LAKEGEN_CONTEXT_WINDOW", "1000")
    monkeypatch.setenv("LAKEGEN_CONTEXT_RESERVE_RATIO", "0.25")

    policy = ContextPolicy.from_env()

    assert policy.window == 1_000
    assert policy.input_budget == 750
    assert policy.history_limit == 450
    assert policy.turn_limit == 150


def test_turn_compression_hysteresis() -> None:
    policy = ContextPolicy(
        window=1_000,
        reserve_ratio=0,
        turn_ratio=0.2,
        growth_ratio=0.1,
        max_turn_compressions=2,
    )
    state = TurnCompressionState()

    assert state.needs(policy.turn_limit - 1, policy) is False
    assert state.needs(policy.turn_limit, policy) is True

    state.record(300)
    assert state.needs(300 + policy.growth_limit - 1, policy) is False
    assert state.needs(300 + policy.growth_limit, policy) is True

    state.record(400)
    # The per-turn cap wins even when the turn keeps growing.
    assert state.needs(10_000, policy) is False
