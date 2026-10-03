"""Tests for session-scoped catalog selection."""

from dataclasses import replace
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from lakegen.agent import (
    AgentConfig,
    AgentLoopFailure,
    AgentLoopResult,
    Conversation,
    StopReason,
)
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.inference import Message, Role
from lakegen.core.persistence import PostgresPersistence
from lakegen.session import Environment, SessionManager


@pytest.fixture()
def registered_catalogs():
    return ("prod", "staging")


def _config() -> AgentConfig:
    return AgentConfig(
        model="test-model",
        system_prompt="test",
        provider="openai",
        max_turns=3,
    )


def _env(agent_turn_repository=None):
    catalogs = MagicMock()

    def require(name):
        if name == "missing":
            raise BaseError(ErrorCode.NOT_FOUND, "Catalog is not registered.")

    catalogs.require.side_effect = require
    persistence = MagicMock(spec=PostgresPersistence)
    persistence.configured = False
    return replace(
        Environment.default(),
        catalog_service=catalogs,
        persistence=persistence,
        session_repository=MagicMock(),
        agent_turn_repository=(
            agent_turn_repository
            if agent_turn_repository is not None
            else MagicMock()
        ),
    )


def test_send_uses_per_turn_model(registered_catalogs, monkeypatch):
    mgr = SessionManager(env=_env())
    session = mgr.create(_config(), owner_id="user-1", catalog_name="prod")

    captured: dict = {}

    def fake_invoke(*, agent_config, **kwargs):
        captured["model"] = agent_config.model
        return AgentLoopResult(
            final_message="ok",
            turn_messages=Conversation(),
            stop_reason=StopReason.COMPLETED,
        )

    monkeypatch.setattr(session._loop, "invoke", fake_invoke)

    session.send("hello", model="other-model")
    assert captured["model"] == "other-model"
    assert session.state.config.model == "test-model"


def test_send_assigns_and_persists_turn_id(registered_catalogs, monkeypatch):
    agent_turn_repository = MagicMock()
    session = SessionManager(env=_env(agent_turn_repository)).create(
        _config(),
        owner_id="user-1",
        catalog_name="prod",
    )
    turn_messages = Conversation(
        messages=[
            Message(role=Role.USER, content="hello"),
            Message(role=Role.ASSISTANT, content="ok"),
        ]
    )
    loop_result = AgentLoopResult(
        final_message="ok",
        turn_messages=turn_messages,
        stop_reason=StopReason.COMPLETED,
    )
    monkeypatch.setattr(session._loop, "invoke", lambda **kwargs: loop_result)

    turn = session.send("hello")

    UUID(turn.id)
    assert turn.result is loop_result
    agent_turn_repository.create.assert_called_once_with(
        {
            "id": turn.id,
            "session_id": session.id,
            "result": {
                "final_message": "ok",
                "turn_messages": {
                    "messages": [
                        {
                            "role": "user",
                            "content": "hello",
                            "tool_calls": None,
                            "tool_call_id": None,
                            "tool_name": None,
                        },
                        {
                            "role": "assistant",
                            "content": "ok",
                            "tool_calls": None,
                            "tool_call_id": None,
                            "tool_name": None,
                        },
                    ]
                },
                "stop_reason": "completed",
            },
        }
    )
    assert session.state.messages.messages == turn_messages.messages


def test_send_persists_and_commits_crashed_turn(registered_catalogs, monkeypatch):
    agent_turn_repository = MagicMock()
    session = SessionManager(env=_env(agent_turn_repository)).create(
        _config(),
        owner_id="user-1",
        catalog_name="prod",
    )
    turn_messages = Conversation(
        messages=[
            Message(role=Role.USER, content="hello"),
            Message(role=Role.SYSTEM, content="Turn crashed."),
        ]
    )
    loop_result = AgentLoopResult(
        final_message="",
        turn_messages=turn_messages,
        stop_reason=StopReason.INTERNAL_ERROR,
    )
    error = RuntimeError("provider disconnected")

    def fail_invoke(**kwargs):
        raise AgentLoopFailure(loop_result, error)

    monkeypatch.setattr(session._loop, "invoke", fail_invoke)

    with pytest.raises(RuntimeError, match="provider disconnected"):
        session.send("hello")

    agent_turn_repository.create.assert_called_once()
    assert session.state.messages.messages == turn_messages.messages


def test_send_rejects_catalog_change(registered_catalogs, monkeypatch):
    mgr = SessionManager(env=_env())
    session = mgr.create(_config(), owner_id="user-1", catalog_name="prod")
    monkeypatch.setattr(
        session._loop,
        "invoke",
        lambda **kwargs: AgentLoopResult(
            final_message="ok",
            turn_messages=Conversation(),
            stop_reason=StopReason.COMPLETED,
        ),
    )

    session.send("hello")

    with pytest.raises(BaseError, match="cannot be changed"):
        session.send("again", catalog_name="staging")


def test_send_unknown_catalog_raises(registered_catalogs):
    mgr = SessionManager(env=_env())
    session = mgr.create(_config(), owner_id="user-1")
    with pytest.raises(BaseError, match="not registered"):
        session.send("hello", catalog_name="missing")
