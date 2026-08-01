"""Tests for lakegen.session.manager.SessionManager."""

import pytest

from lakegen.agent import AgentConfig
from lakegen.core.error.base import BaseError
from lakegen.session import Environment, SessionManager


def _config(**overrides) -> AgentConfig:
    base = dict(
        model="test-model",
        system_prompt="test",
        provider="openai",
        max_turns=3,
    )
    base.update(overrides)
    return AgentConfig(**base)


def test_create_get_list():
    mgr = SessionManager(env=Environment.default())
    a = mgr.create(_config())
    b = mgr.create(_config())

    assert mgr.get(a.id) is a
    assert mgr.get(b.id) is b
    assert {s.id for s in mgr.list()} == {a.id, b.id}


def test_spawn_shares_env_and_sets_parent():
    mgr = SessionManager(env=Environment.default())
    parent = mgr.create(_config())
    child = parent.spawn(_config(system_prompt="child"))

    assert child.parent_id == parent.id
    assert child.id in parent.state.children
    assert child.env is parent.env
    assert child.state.messages.messages == []


def test_delete_removes_children_and_unlinks_parent():
    mgr = SessionManager(env=Environment.default())
    parent = mgr.create(_config())
    child = parent.spawn(_config())
    grandchild = child.spawn(_config())

    mgr.delete(child.id)

    assert child.id not in parent.state.children
    with pytest.raises(BaseError):
        mgr.get(child.id)
    with pytest.raises(BaseError):
        mgr.get(grandchild.id)
    assert mgr.get(parent.id) is parent


def test_get_missing_raises():
    mgr = SessionManager(env=Environment.default())
    with pytest.raises(BaseError):
        mgr.get(999)


def test_create_with_missing_parent_raises():
    mgr = SessionManager(env=Environment.default())
    with pytest.raises(BaseError):
        mgr.create(_config(), parent_id=42)
