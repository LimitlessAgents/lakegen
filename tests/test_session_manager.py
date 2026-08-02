"""Tests for lakegen.session.manager.SessionManager."""

import threading
import time

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


def test_delete_closes_session_so_send_and_spawn_fail():
    mgr = SessionManager(env=Environment.default())
    session = mgr.create(_config())

    mgr.delete(session.id)

    assert session.state.closed is True
    with pytest.raises(BaseError, match="closed"):
        session.send("hello")
    with pytest.raises(BaseError, match="closed"):
        session.spawn(_config())


def test_delete_closes_cascaded_children():
    mgr = SessionManager(env=Environment.default())
    parent = mgr.create(_config())
    child = parent.spawn(_config())
    grandchild = child.spawn(_config())

    mgr.delete(parent.id)

    assert parent.state.closed is True
    assert child.state.closed is True
    assert grandchild.state.closed is True
    with pytest.raises(BaseError, match="closed"):
        child.send("hello")
    with pytest.raises(BaseError, match="closed"):
        grandchild.spawn(_config())


def test_close_blocks_further_send_and_spawn():
    mgr = SessionManager(env=Environment.default())
    session = mgr.create(_config())

    session.close()

    assert session.state.closed is True
    with pytest.raises(BaseError, match="closed"):
        session.send("hello")
    with pytest.raises(BaseError, match="closed"):
        session.spawn(_config())
    # Still registered until delete; close alone does not unregister.
    assert mgr.get(session.id) is session


def test_delete_does_not_hold_manager_lock_while_closing():
    """Other sessions stay usable while delete waits on an in-flight turn lock."""
    mgr = SessionManager(env=Environment.default())
    active = mgr.create(_config())
    other = mgr.create(_config())

    holding = threading.Event()
    release = threading.Event()

    def hold_session_lock() -> None:
        with active._lock:
            holding.set()
            release.wait(timeout=5)

    holder = threading.Thread(target=hold_session_lock)
    holder.start()
    assert holding.wait(timeout=1)

    delete_done = threading.Event()

    def do_delete() -> None:
        mgr.delete(active.id)
        delete_done.set()

    deleter = threading.Thread(target=do_delete)
    deleter.start()

    deadline = time.time() + 2
    while time.time() < deadline:
        try:
            mgr.get(active.id)
        except BaseError:
            break
        time.sleep(0.01)
    else:
        release.set()
        holder.join(timeout=1)
        deleter.join(timeout=1)
        pytest.fail("delete never unregistered the active session")

    # Unregistered but not yet closed — close is blocked on session._lock.
    assert active.state.closed is False
    assert mgr.get(other.id) is other
    created = mgr.create(_config())
    assert mgr.get(created.id) is created

    release.set()
    holder.join(timeout=2)
    deleter.join(timeout=2)
    assert delete_done.is_set()
    assert active.state.closed is True
