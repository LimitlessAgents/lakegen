import threading
from dataclasses import replace
from unittest.mock import MagicMock

from lakegen.agent import AgentConfig, AgentLoopResult, CompressionEvent, Conversation
from lakegen.agent.model import CompressionScope, StopReason
from lakegen.core.persistence import PostgresPersistence
from lakegen.inference import Message, Role
from lakegen.session import Environment, Session, SessionManager
from lakegen.session.context import Compression, ContextMeasurement
from tests.conftest import open_session


def _persistence() -> MagicMock:
    persistence = MagicMock(spec=PostgresPersistence)
    persistence.transaction.return_value.__enter__.return_value = MagicMock()
    return persistence


def _config() -> AgentConfig:
    return AgentConfig(
        model="test-model",
        system_prompt="test",
        provider="openai",
        max_turns=3,
    )


def _env() -> Environment:
    env = Environment.default()
    context_engine = MagicMock()
    context_engine.measure.return_value = ContextMeasurement(
        total=10,
        history=10,
        turn=0,
        source="estimated",
    )
    agent_turn_repository = MagicMock()
    agent_turn_repository.create.return_value = 10
    agent_turn_repository.latest_id.return_value = 9
    session_repository = MagicMock()
    session_repository.exists.return_value = True
    session_repository.get.return_value = {
        "id": "session-1",
        "owner_id": "user-1",
        "catalog_name": "prod",
    }
    return replace(
        env,
        catalog_service=MagicMock(),
        persistence=_persistence(),
        context_engine=context_engine,
        session_repository=session_repository,
        agent_turn_repository=agent_turn_repository,
    )


def _session(env: Environment) -> "Session":
    return open_session(
        SessionManager(env=env),
        _config(),
        owner_id="user-1",
        catalog_name="prod",
    )


def _compression(summary: str = "summary") -> Compression:
    message = Message(role=Role.USER, content=summary, is_summary=True)
    return Compression(
        scope=CompressionScope.HISTORY,
        messages=Conversation(messages=[message]),
        summary=message,
        replaced_messages=2,
    )


def test_history_compression_replaces_state_and_marks_the_turn() -> None:
    env = _env()
    env.context_engine.measure.side_effect = [
        ContextMeasurement(
            total=200_000,
            history=200_000,
            turn=0,
            source="estimated",
        ),
        ContextMeasurement(
            total=1_000,
            history=1_000,
            turn=0,
            source="estimated",
        ),
    ]
    env.context_engine.compress.return_value = _compression()
    env.context_engine.estimate_messages.side_effect = [1_000, 10]
    session = _session(env)
    session.state.messages.messages = [
        Message(role=Role.USER, content="old"),
        Message(role=Role.ASSISTANT, content="old answer"),
    ]

    session._compress_history(_config(), "system", [], threading.Event())

    env.agent_turn_repository.update_summary.assert_called_once_with(
        9,
        summary="summary",
        summary_kind="history",
        context_tokens=1_000,
        context_source="estimated",
    )
    assert [message.content for message in session.state.messages.messages] == [
        "summary"
    ]


def test_history_compression_failure_keeps_raw_history() -> None:
    env = _env()
    env.context_engine.measure.return_value = ContextMeasurement(
        total=200_000,
        history=200_000,
        turn=0,
        source="estimated",
    )
    env.context_engine.compress.side_effect = RuntimeError("provider down")
    session = _session(env)
    session.state.messages.messages = [
        Message(role=Role.USER, content="old"),
    ]

    session._compress_history(_config(), "system", [], threading.Event())

    env.agent_turn_repository.update_summary.assert_not_called()
    assert [message.content for message in session.state.messages.messages] == ["old"]


def test_history_compression_without_progress_is_discarded() -> None:
    env = _env()
    env.context_engine.measure.side_effect = [
        ContextMeasurement(
            total=200_000,
            history=200_000,
            turn=0,
            source="estimated",
        ),
        ContextMeasurement(
            total=200_000,
            history=200_000,
            turn=0,
            source="estimated",
        ),
    ]
    env.context_engine.compress.return_value = _compression()
    env.context_engine.estimate_messages.side_effect = [1_000, 1_000]
    session = _session(env)
    session.state.messages.messages = [
        Message(role=Role.USER, content="old"),
    ]

    session._compress_history(_config(), "system", [], threading.Event())

    env.agent_turn_repository.update_summary.assert_not_called()
    assert [message.content for message in session.state.messages.messages] == ["old"]


def test_send_persists_the_visible_turn_and_compression_events(monkeypatch) -> None:
    env = _env()
    session = _session(env)
    result = AgentLoopResult(
        final_message="ok",
        turn_messages=Conversation(
            messages=[
                Message(role=Role.USER, content="hi"),
                Message(role=Role.ASSISTANT, content="ok"),
            ]
        ),
        stop_reason=StopReason.COMPLETED,
        compression_events=(
            CompressionEvent(
                scope=CompressionScope.TURN,
                summary="condensed",
                replaced_messages=2,
            ),
        ),
    )
    monkeypatch.setattr(session._loop, "invoke", lambda **kwargs: result)

    session.send("hi")

    payload = env.agent_turn_repository.create.call_args.args[0]
    assert payload["result"]["turn_messages"]["messages"][0]["content"] == "hi"
    assert payload["result"]["compression_events"] == [
        {
            "scope": "turn",
            "summary": "condensed",
            "replaced_messages": 2,
        }
    ]
    assert payload["context_tokens"] == 10
    assert payload["context_source"] == "estimated"
    assert session.state.messages.messages == result.turn_messages.messages
    env.agent_turn_repository.update_summary.assert_not_called()


def test_send_compresses_history_against_the_new_turn(monkeypatch) -> None:
    env = _env()
    session = _session(env)
    result = AgentLoopResult(
        final_message="ok",
        turn_messages=Conversation(messages=[Message(role=Role.USER, content="hi")]),
        stop_reason=StopReason.COMPLETED,
    )
    monkeypatch.setattr(session._loop, "invoke", lambda **kwargs: result)
    calls = []
    monkeypatch.setattr(
        session,
        "_compress_history",
        lambda *args, **kwargs: calls.append(kwargs),
    )

    session.send("hi")

    assert calls[-1] == {"last_turn_id": 10}
