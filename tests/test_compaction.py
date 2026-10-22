import threading
from unittest.mock import MagicMock

from lakegen.agent import AgentConfig, AgentLoopResult, Conversation, StopReason
from lakegen.inference import Message, Role, StreamChunk
from lakegen.session import Environment, SessionManager
from lakegen.session.compaction import compact
from lakegen.tool.model import ToolCall
from tests.conftest import open_session


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
            Message(role=Role.USER, content="Count rows in users table"),
            Message(
                role=Role.ASSISTANT,
                content=None,
                tool_calls=[
                    ToolCall("call-1", "run_query", {"sql": "SELECT count(*) FROM users"})
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

    result = compact(
        inference_router=router,
        provider="openai",
        model="gpt-4o",
        conversation=conversation,
        cancel_event=threading.Event(),
    )

    assert result.role == Role.USER
    assert result.content == "Summary: table has 42,000 rows."

    assert captured_request is not None
    # All messages including tool outputs were provided to the summarizer
    request_roles = [msg.role for msg in captured_request.messages]
    assert request_roles == [
        Role.USER,
        Role.ASSISTANT,
        Role.TOOL,
        Role.ASSISTANT,
        Role.USER,
    ]
    # Check that the tool fact reached the request
    tool_message = captured_request.messages[2]
    assert '{"count": 42000, "status": "success"}' in (tool_message.content or "")
    # Check that summarizer prompt was appended
    assert captured_request.messages[-1].content == "Now write the compacted summary of the conversation above."


def test_compact_aborts_on_cancel_event() -> None:
    router = MagicMock()
    cancel_event = threading.Event()

    def fake_stream(provider, request, *, cancel_event):
        yield StreamChunk(text="Start of summary...")
        cancel_event.set()
        yield StreamChunk(text="More summary that should be ignored.")

    router.stream.side_effect = fake_stream

    conversation = Conversation(
        messages=[Message(role=Role.USER, content="hello")]
    )

    result = compact(
        inference_router=router,
        provider="openai",
        model="gpt-4o",
        conversation=conversation,
        cancel_event=cancel_event,
    )

    assert result.content == ""


def test_failed_compaction_write_restores_messages(monkeypatch) -> None:
    compaction_repository = MagicMock()
    agent_turn_repository = MagicMock()
    session_repository = MagicMock()
    router = MagicMock()

    def fake_stream(provider, request, *, cancel_event):
        yield StreamChunk(text="Compacted conversation summary")

    router.stream.side_effect = fake_stream

    env = Environment.default()
    env = Environment(
        tool_registry=env.tool_registry,
        catalog_service=env.catalog_service,
        inference_registry=env.inference_registry,
        inference_router=router,
        persistence=env.persistence,
        session_repository=session_repository,
        agent_turn_repository=agent_turn_repository,
        compaction_repository=compaction_repository,
        token_budget=env.token_budget,
    )

    session_repository.exists.return_value = True
    session_repository.get.return_value = {
        "id": "session-1",
        "owner_id": "user-1",
        "catalog_name": "prod",
    }
    compaction_repository.list.return_value = []

    # Simulate database error on writing compaction
    compaction_repository.create.side_effect = RuntimeError("DB write failed: disk full")

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
    # Force compaction check to trigger
    monkeypatch.setattr(session, "_check_if_compaction_needed", lambda: True)

    turn = session.send("turn 1 text")

    # Turn succeeds despite compaction failure
    assert turn.result is loop_result
    # Compaction create was attempted
    compaction_repository.create.assert_called_once()
    # Messages were restored to state_copy rather than left empty or overwritten
    assert session.state.messages.messages == turn_messages.messages


def test_compaction_forwards_the_session_endpoint() -> None:
    captured = []
    router = MagicMock()

    def fake_stream(provider, request, *, cancel_event):
        captured.append(request)
        yield StreamChunk(text="Compacted conversation summary")

    router.stream.side_effect = fake_stream

    compact(
        inference_router=router,
        provider="openai",
        model="gpt-4o",
        conversation=Conversation(messages=[Message(role=Role.USER, content="hello")]),
        cancel_event=threading.Event(),
        base_url="https://openrouter.ai/api/v1",
    )

    assert [request.base_url for request in captured] == ["https://openrouter.ai/api/v1"]


def test_compaction_without_an_endpoint_uses_the_sdk_default() -> None:
    captured = []
    router = MagicMock()

    def fake_stream(provider, request, *, cancel_event):
        captured.append(request)
        yield StreamChunk(text="Compacted conversation summary")

    router.stream.side_effect = fake_stream

    compact(
        inference_router=router,
        provider="openai",
        model="gpt-4o",
        conversation=Conversation(messages=[Message(role=Role.USER, content="hello")]),
        cancel_event=threading.Event(),
    )

    assert [request.base_url for request in captured] == [None]
