"""Tests for session-scoped catalog selection."""

import json

import pytest

from lakegen.agent import AgentConfig, AgentLoopResult, Conversation, StopReason
from lakegen.core.credential import json_store
from lakegen.core.error.base import BaseError
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


def test_send_uses_per_turn_model(registered_catalogs, monkeypatch):
    mgr = SessionManager(env=Environment.default())
    session = mgr.create(_config(), owner_id="user-1", catalog_name="prod")

    captured: dict = {}

    def fake_invoke(*, agent_config, **kwargs):
        captured["model"] = agent_config.model
        return AgentLoopResult(
            final_message="ok",
            transcript=Conversation(),
            stop_reason=StopReason.COMPLETED,
        )

    monkeypatch.setattr(session._loop, "invoke", fake_invoke)

    session.send("hello", model="other-model")
    assert captured["model"] == "other-model"
    assert session.state.config.model == "test-model"


def test_send_switches_catalog(registered_catalogs, monkeypatch):
    mgr = SessionManager(env=Environment.default())
    session = mgr.create(_config(), owner_id="user-1", catalog_name="prod")

    captured: dict = {}

    def fake_invoke(*, catalog_name, catalog_switched_from, **kwargs):
        captured["catalog_name"] = catalog_name
        captured["catalog_switched_from"] = catalog_switched_from
        return AgentLoopResult(
            final_message="ok",
            transcript=Conversation(),
            stop_reason=StopReason.COMPLETED,
        )

    monkeypatch.setattr(session._loop, "invoke", fake_invoke)

    session.send("hello", catalog_name="staging")

    assert session.state.catalog_name == "staging"
    assert captured["catalog_name"] == "staging"
    assert captured["catalog_switched_from"] == "prod"


def test_send_same_catalog_does_not_mark_switch(registered_catalogs, monkeypatch):
    mgr = SessionManager(env=Environment.default())
    session = mgr.create(_config(), owner_id="user-1", catalog_name="prod")

    captured: dict = {}

    def fake_invoke(*, catalog_name, catalog_switched_from, **kwargs):
        captured["catalog_switched_from"] = catalog_switched_from
        return AgentLoopResult(
            final_message="ok",
            transcript=Conversation(),
            stop_reason=StopReason.COMPLETED,
        )

    monkeypatch.setattr(session._loop, "invoke", fake_invoke)

    session.send("hello", catalog_name="prod")
    assert captured["catalog_switched_from"] is None


def test_send_unknown_catalog_raises(registered_catalogs):
    mgr = SessionManager(env=Environment.default())
    session = mgr.create(_config(), owner_id="user-1", catalog_name="prod")
    with pytest.raises(BaseError, match="not registered"):
        session.send("hello", catalog_name="missing")
