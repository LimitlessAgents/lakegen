"""Tests for session-scoped catalog selection."""

import json
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
from lakegen.core.credential import json_store
from lakegen.core.error.base import BaseError
from lakegen.inference import Message, Role
from lakegen.session import Environment, SessionManager


@pytest.fixture()
def registered_catalogs(tmp_path, monkeypatch):
    cred = tmp_path / "credentials.json"
    cred.write_text(json.dumps({}))
    cred.chmod(0o600)
    monkeypatch.setattr(json_store, "CREDENTIALS_PATH", str(cred))
    monkeypatch.setattr(json_store, "_path", lambda: str(cred))
    for name in ("prod", "staging"):
        json_store.store(
            "catalog",
            name,
            {
                "lakehouse": "iceberg",
                "catalog_type": "rest",
                "warehouse": f"s3://{name}",
            },
        )


def _config() -> AgentConfig:
    return AgentConfig(
        model="test-model",
        system_prompt="test",
        provider="openai",
        max_turns=3,
    )


def _env(persistence=None):
    return replace(
        Environment.default(),
        persistence=persistence if persistence is not None else MagicMock(),
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
    persistence = MagicMock()
    session = SessionManager(env=_env(persistence)).create(
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
    persistence.store_turn.assert_called_once_with(
        session_id=session.id,
        turn_id=turn.id,
        result={
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
    )
    assert session.state.messages.messages == turn_messages.messages


def test_send_persists_and_commits_crashed_turn(registered_catalogs, monkeypatch):
    persistence = MagicMock()
    session = SessionManager(env=_env(persistence)).create(
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

    persistence.store_turn.assert_called_once()
    assert session.state.messages.messages == turn_messages.messages


def test_send_switches_catalog(registered_catalogs, monkeypatch):
    mgr = SessionManager(env=_env())
    session = mgr.create(_config(), owner_id="user-1", catalog_name="prod")

    captured: dict = {}

    def fake_invoke(*, catalog_name, catalog_switched_from, **kwargs):
        captured["catalog_name"] = catalog_name
        captured["catalog_switched_from"] = catalog_switched_from
        return AgentLoopResult(
            final_message="ok",
            turn_messages=Conversation(),
            stop_reason=StopReason.COMPLETED,
        )

    monkeypatch.setattr(session._loop, "invoke", fake_invoke)

    session.send("hello", catalog_name="staging")

    assert session.state.catalog_name == "staging"
    assert captured["catalog_name"] == "staging"
    assert captured["catalog_switched_from"] == "prod"


def test_send_same_catalog_does_not_mark_switch(registered_catalogs, monkeypatch):
    mgr = SessionManager(env=_env())
    session = mgr.create(_config(), owner_id="user-1", catalog_name="prod")

    captured: dict = {}

    def fake_invoke(*, catalog_name, catalog_switched_from, **kwargs):
        captured["catalog_switched_from"] = catalog_switched_from
        return AgentLoopResult(
            final_message="ok",
            turn_messages=Conversation(),
            stop_reason=StopReason.COMPLETED,
        )

    monkeypatch.setattr(session._loop, "invoke", fake_invoke)

    session.send("hello", catalog_name="prod")
    assert captured["catalog_switched_from"] is None


def test_send_unknown_catalog_raises(registered_catalogs):
    mgr = SessionManager(env=_env())
    session = mgr.create(_config(), owner_id="user-1", catalog_name="prod")
    with pytest.raises(BaseError, match="not registered"):
        session.send("hello", catalog_name="missing")
