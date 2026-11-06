import threading
from dataclasses import replace
from unittest.mock import MagicMock

from lakegen.agent import AgentConfig, AgentLoopResult, Conversation, StopReason
from lakegen.inference import Message, Role, StreamChunk
from lakegen.session import Environment, SessionManager
from lakegen.session.context import ContextEngine
from lakegen.tool.model import ToolCall
from tests.conftest import open_session


def _persistence() -> MagicMock:
    persistence = MagicMock()
    persistence.transaction.return_value.__enter__.return_value = MagicMock()
    return persistence


def test_tool_facts_reach_summarizer() -> None:
    router = MagicMock()
    captured_request = None

    def fake_stream(provider, request, *, cancel_event):
        nonlocal captured_request
        captured_request = request
        yield StreamChunk(text="Summary: table has 42,000 rows.")

    router.stream.side_effect = fake_stream

    conversation = Conversation(
        messages=[
            Message(role=Role.USER, content="Earlier question"),
            Message(role=Role.ASSISTANT, content="Earlier answer"),
            Message(role=Role.USER, content="Count rows in users table"),
            Message(
                role=Role.ASSISTANT,
                content=None,
                tool_calls=[
                    ToolCall(
                        "call-1", "run_query", {"sql": "SELECT count(*) FROM users"}
                    )
                ],
            ),
            Message(
                role=Role.TOOL,
                content='{"count": 42000, "status": "success"}',
                tool_call_id="call-1",
                tool_name="run_query",
            ),
            Message(
                role=Role.ASSISTANT,
                content="There are 42,000 rows in the users table.",
            ),
        ]
    )

    compressed = ContextEngine().compress(
        conversation,
        budget_tokens=1,
        router=router,
        provider="openai",
        model="gpt-4o",
        cancel_event=threading.Event(),
    )
    result = compressed.messages[0]

    assert result.role == Role.USER
    assert result.content == "Summary: table has 42,000 rows."

    assert captured_request is not None
    # All messages including tool outputs were provided to the summarizer
    request_roles = [msg.role for msg in captured_request.messages]
    assert request_roles == [
        Role.USER,
        Role.ASSISTANT,
        Role.USER,
        Role.ASSISTANT,
        Role.TOOL,
        Role.ASSISTANT,
        Role.USER,
    ]
    # Check that the tool fact reached the request
    tool_message = captured_request.messages[4]
    assert '{"count": 42000, "status": "success"}' in (tool_message.content or "")
    # Check that summarizer prompt was appended
    assert (
        captured_request.messages[-1].content
        == "Now write the compressed summary of the conversation above."
    )


def test_compress_aborts_on_cancel_event() -> None:
    router = MagicMock()
    cancel_event = threading.Event()

    def fake_stream(provider, request, *, cancel_event):
        yield StreamChunk(text="Start of summary...")
        cancel_event.set()
        yield StreamChunk(text="More summary that should be ignored.")

    router.stream.side_effect = fake_stream

    conversation = Conversation(messages=[Message(role=Role.USER, content="hello")])

    result = ContextEngine().compress(
        conversation,
        budget_tokens=1,
        router=router,
        provider="openai",
        model="gpt-4o",
        cancel_event=cancel_event,
    )

    assert result is conversation


def test_failed_compression_write_restores_messages(monkeypatch) -> None:
    compression_repository = MagicMock()
    agent_turn_repository = MagicMock()
    session_repository = MagicMock()
    catalog_service = MagicMock()
    router = MagicMock()

    def fake_stream(provider, request, *, cancel_event):
        yield StreamChunk(text="Compressed conversation summary")

    router.stream.side_effect = fake_stream

    env = Environment.default()
    env = Environment(
        tool_registry=env.tool_registry,
        catalog_service=catalog_service,
        inference_registry=env.inference_registry,
        inference_router=router,
        persistence=_persistence(),
        context_engine=env.context_engine,
        session_repository=session_repository,
        agent_turn_repository=agent_turn_repository,
        compression_repository=compression_repository,
        token_budget=env.token_budget,
    )

    session_repository.exists.return_value = True
    session_repository.get.return_value = {
        "id": "session-1",
        "owner_id": "user-1",
        "catalog_name": "prod",
    }
    agent_turn_repository.latest_id.return_value = None
    compression_repository.list.return_value = []

    # Simulate database error on writing compression
    compression_repository.create.side_effect = RuntimeError(
        "DB write failed: disk full"
    )

    mgr = SessionManager(env=env)
    session = open_session(
        mgr,
        AgentConfig(
            model="test-model",
            system_prompt="test",
            provider="openai",
            max_turns=3,
        ),
        owner_id="user-1",
        catalog_name="prod",
    )

    turn_messages = Conversation(
        messages=[
            Message(role=Role.USER, content="turn 1 text"),
            Message(role=Role.ASSISTANT, content="turn 1 answer"),
        ]
    )
    loop_result = AgentLoopResult(
        final_message="turn 1 answer",
        turn_messages=turn_messages,
        stop_reason=StopReason.COMPLETED,
    )
    monkeypatch.setattr(session._loop, "invoke", lambda **kwargs: loop_result)
    monkeypatch.setattr(
        env.context_engine,
        "needs_compression",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        env.context_engine,
        "compress",
        lambda *args, **kwargs: Conversation(
            messages=[
                Message(
                    role=Role.USER,
                    content="summary",
                    is_summary=True,
                )
            ]
        ),
    )

    turn = session.send("turn 1 text")

    # Turn succeeds despite compression failure
    assert turn.result is loop_result
    # Compression create was attempted
    compression_repository.create.assert_called_once()
    # Messages were restored to state_copy rather than left empty or overwritten
    assert session.state.messages.messages == turn_messages.messages


def test_compressed_result_replaces_state_without_storing_the_tail(monkeypatch) -> None:
    env = Environment.default()
    compression_repository = MagicMock()
    compression_repository.list.return_value = []
    agent_turn_repository = MagicMock()
    agent_turn_repository.latest_id.return_value = None
    agent_turn_repository.create.side_effect = [10]
    session_repository = MagicMock()
    session_repository.exists.return_value = True
    session_repository.get.return_value = {
        "id": "session-1",
        "owner_id": "user-1",
        "catalog_name": "prod",
    }
    env = replace(
        env,
        catalog_service=MagicMock(),
        persistence=_persistence(),
        session_repository=session_repository,
        agent_turn_repository=agent_turn_repository,
        compression_repository=compression_repository,
    )
    mgr = SessionManager(env=env)
    session = open_session(
        mgr,
        AgentConfig(
            model="test-model",
            system_prompt="test",
            provider="openai",
            max_turns=3,
        ),
        owner_id="user-1",
        catalog_name="prod",
    )

    compressed = Conversation(
        messages=[
            Message(role=Role.USER, content="summary", is_summary=True),
            Message(role=Role.USER, content="recent", is_tail=True),
        ]
    )
    loop_result = AgentLoopResult(
        final_message="ok",
        turn_messages=Conversation(
            messages=[Message(role=Role.USER, content="turn")],
        ),
        stop_reason=StopReason.COMPLETED,
        compressed=compressed,
    )
    monkeypatch.setattr(session._loop, "invoke", lambda **kwargs: loop_result)

    turn = session.send("turn")

    assert turn.id == 10
    assert session.state.messages is compressed
    compression_repository.create.assert_called_once()
    assert compression_repository.create.call_args.args[0] == {
        "data": "summary",
        "session_id": session.id,
        "last_compressed_turn_id": 10,
    }
    # The tail is never written as a turn: only the raw turn row is stored.
    assert agent_turn_repository.create.call_count == 1
    raw_result = agent_turn_repository.create.call_args.args[0]["result"]
    assert raw_result["turn_messages"]["messages"][0]["content"] == "turn"
    assert raw_result["compressed"] is None


def test_compression_runs_before_a_turn(monkeypatch) -> None:
    env = Environment.default()
    context = MagicMock()
    context.needs_compression.side_effect = [True, False]
    context.compress.return_value = Conversation(
        messages=[
            Message(role=Role.USER, content="summary", is_summary=True),
            Message(role=Role.USER, content="tail"),
        ]
    )
    compression_repository = MagicMock()
    compression_repository.list.return_value = []
    agent_turn_repository = MagicMock()
    agent_turn_repository.latest_id.return_value = 7
    agent_turn_repository.create.side_effect = [8]
    session_repository = MagicMock()
    session_repository.exists.return_value = True
    session_repository.get.return_value = {
        "id": "session-1",
        "owner_id": "user-1",
        "catalog_name": "prod",
    }
    env = replace(
        env,
        catalog_service=MagicMock(),
        persistence=_persistence(),
        context_engine=context,
        session_repository=session_repository,
        agent_turn_repository=agent_turn_repository,
        compression_repository=compression_repository,
    )
    session = open_session(
        SessionManager(env=env),
        AgentConfig(
            model="test-model",
            system_prompt="test",
            provider="openai",
            max_turns=3,
        ),
        owner_id="user-1",
        catalog_name="prod",
    )
    session.state.messages.messages = [
        Message(role=Role.USER, content="old"),
        Message(role=Role.ASSISTANT, content="old answer"),
    ]
    loop_result = AgentLoopResult(
        final_message="ok",
        turn_messages=Conversation(
            messages=[Message(role=Role.USER, content="new")],
        ),
        stop_reason=StopReason.COMPLETED,
    )
    monkeypatch.setattr(session._loop, "invoke", lambda **kwargs: loop_result)

    turn = session.send("new")

    assert turn.id == 8
    compression_repository.create.assert_called_once()
    assert compression_repository.create.call_args.args[0] == {
        "data": "summary",
        "session_id": session.id,
        "last_compressed_turn_id": 7,
    }
    assert session.state.messages.messages[0].is_summary is True
    assert session.state.messages.messages[-1].content == "new"


def test_compression_runs_after_a_turn(monkeypatch) -> None:
    env = Environment.default()
    context = MagicMock()
    context.needs_compression.return_value = True
    context.compress.return_value = Conversation(
        messages=[
            Message(role=Role.USER, content="summary", is_summary=True),
            Message(role=Role.USER, content="tail"),
        ]
    )
    compression_repository = MagicMock()
    compression_repository.list.return_value = []
    agent_turn_repository = MagicMock()
    agent_turn_repository.latest_id.return_value = None
    agent_turn_repository.create.side_effect = [5, 6]
    session_repository = MagicMock()
    session_repository.exists.return_value = True
    session_repository.get.return_value = {
        "id": "session-1",
        "owner_id": "user-1",
        "catalog_name": "prod",
    }
    env = replace(
        env,
        catalog_service=MagicMock(),
        persistence=_persistence(),
        context_engine=context,
        session_repository=session_repository,
        agent_turn_repository=agent_turn_repository,
        compression_repository=compression_repository,
    )
    session = open_session(
        SessionManager(env=env),
        AgentConfig(
            model="test-model",
            system_prompt="test",
            provider="openai",
            max_turns=3,
        ),
        owner_id="user-1",
        catalog_name="prod",
    )
    loop_result = AgentLoopResult(
        final_message="ok",
        turn_messages=Conversation(
            messages=[Message(role=Role.USER, content="new")],
        ),
        stop_reason=StopReason.COMPLETED,
    )
    monkeypatch.setattr(session._loop, "invoke", lambda **kwargs: loop_result)

    turn = session.send("new")

    assert turn.id == 5
    compression_repository.create.assert_called_once()
    assert compression_repository.create.call_args.args[0] == {
        "data": "summary",
        "session_id": session.id,
        "last_compressed_turn_id": 5,
    }
    assert session.state.messages.messages[0].is_summary is True


def test_compression_forwards_the_session_endpoint() -> None:
    captured = []
    router = MagicMock()

    def fake_stream(provider, request, *, cancel_event):
        captured.append(request)
        yield StreamChunk(text="Compressed conversation summary")

    router.stream.side_effect = fake_stream

    ContextEngine().compress(
        Conversation(
            messages=[
                Message(role=Role.USER, content="early"),
                Message(role=Role.ASSISTANT, content="early answer"),
                Message(role=Role.USER, content="hello"),
            ]
        ),
        budget_tokens=1,
        router=router,
        provider="openai",
        model="gpt-4o",
        cancel_event=threading.Event(),
        base_url="https://openrouter.ai/api/v1",
    )

    assert [request.base_url for request in captured] == [
        "https://openrouter.ai/api/v1"
    ]


def test_compression_without_an_endpoint_uses_the_sdk_default() -> None:
    captured = []
    router = MagicMock()

    def fake_stream(provider, request, *, cancel_event):
        captured.append(request)
        yield StreamChunk(text="Compressed conversation summary")

    router.stream.side_effect = fake_stream

    ContextEngine().compress(
        Conversation(
            messages=[
                Message(role=Role.USER, content="early"),
                Message(role=Role.ASSISTANT, content="early answer"),
                Message(role=Role.USER, content="hello"),
            ]
        ),
        budget_tokens=1,
        router=router,
        provider="openai",
        model="gpt-4o",
        cancel_event=threading.Event(),
    )

    assert [request.base_url for request in captured] == [None]
