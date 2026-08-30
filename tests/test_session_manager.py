"""Tests for lakegen.session.manager.SessionManager."""

import json
import threading
import time
from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from lakegen.agent import AgentConfig
from lakegen.core.credential import json_store
from lakegen.core.error.base import BaseError
from lakegen.session import Environment, SessionManager


@pytest.fixture()
def registered_catalog(tmp_path, monkeypatch):
    cred = tmp_path / "credentials.json"
    cred.write_text(json.dumps({}))
    cred.chmod(0o600)
    monkeypatch.setattr(json_store, "CREDENTIALS_PATH", str(cred))
    monkeypatch.setattr(json_store, "_path", lambda: str(cred))
    json_store.store(
        "catalog",
        "prod",
        {
            "lakehouse": "iceberg",
            "catalog_type": "rest",
            "warehouse": "s3://prod",
        },
    )
    json_store.store(
        "catalog",
        "staging",
        {
            "lakehouse": "iceberg",
            "catalog_type": "rest",
            "warehouse": "s3://staging",
        },
    )
    return "prod"


def _config(**overrides) -> AgentConfig:
    base = dict(
        model="test-model",
        system_prompt="test",
        provider="openai",
        max_turns=3,
    )
    base.update(overrides)
    return AgentConfig(**base)


_OWNER = "test-user"


def _env():
    return replace(Environment.default(), persistence=MagicMock())


def test_create_get_list(registered_catalog):
    mgr = SessionManager(env=_env())
    a = mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)
    b = mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)

    assert mgr.get(a.id) is a
    assert mgr.get(b.id) is b
    assert {s.id for s in mgr.list()} == {a.id, b.id}
    assert a.state.catalog_name == registered_catalog


def test_create_without_catalog(registered_catalog):
    mgr = SessionManager(env=_env())
    session = mgr.create(_config(), owner_id=_OWNER)
    assert session.state.catalog_name is None
    assert session.state.owner_id == _OWNER


def test_send_requires_catalog_on_first_turn(registered_catalog):
    mgr = SessionManager(env=_env())
    session = mgr.create(_config(), owner_id=_OWNER)
    with pytest.raises(BaseError, match="catalog_name is required"):
        session.send("hello")


def test_create_unknown_catalog_raises(registered_catalog):
    mgr = SessionManager(env=_env())
    with pytest.raises(BaseError, match="not registered"):
        mgr.create(_config(), owner_id=_OWNER, catalog_name="missing")


def test_spawn_inherits_catalog(registered_catalog):
    mgr = SessionManager(env=_env())
    parent = mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)
    child = parent.spawn(_config(system_prompt="child"))

    assert child.parent_id == parent.id
    assert child.id in parent.state.children
    assert child.env is parent.env
    assert child.state.catalog_name == registered_catalog
    assert child.state.messages.messages == []


def test_delete_removes_children_and_unlinks_parent(registered_catalog):
    mgr = SessionManager(env=_env())
    parent = mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)
    child = parent.spawn(_config())
    grandchild = child.spawn(_config())

    mgr.delete(child.id)

    assert child.id not in parent.state.children
    with pytest.raises(BaseError):
        mgr.get(child.id)
    with pytest.raises(BaseError):
        mgr.get(grandchild.id)
    assert mgr.get(parent.id) is parent


def test_get_missing_raises(registered_catalog):
    mgr = SessionManager(env=_env())
    with pytest.raises(BaseError):
        mgr.get("00000000-0000-0000-0000-000000000099")


def test_create_with_missing_parent_raises(registered_catalog):
    mgr = SessionManager(env=_env())
    with pytest.raises(BaseError):
        mgr.create(
            _config(),
            owner_id=_OWNER,
            catalog_name=registered_catalog,
            parent_id="00000000-0000-0000-0000-000000000042",
        )


def test_delete_closes_session_so_send_and_spawn_fail(registered_catalog):
    mgr = SessionManager(env=_env())
    session = mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)

    mgr.delete(session.id)

    assert session.state.closed is True
    with pytest.raises(BaseError, match="closed"):
        session.send("hello")
    with pytest.raises(BaseError, match="closed"):
        session.spawn(_config())


def test_delete_closes_cascaded_children(registered_catalog):
    mgr = SessionManager(env=_env())
    parent = mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)
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


def test_close_blocks_further_send_and_spawn(registered_catalog):
    mgr = SessionManager(env=_env())
    session = mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)

    session.close()

    assert session.state.closed is True
    with pytest.raises(BaseError, match="closed"):
        session.send("hello")
    with pytest.raises(BaseError, match="closed"):
        session.spawn(_config())
    # Still registered until delete; close alone does not unregister.
    assert mgr.get(session.id) is session


def test_delete_does_not_hold_manager_lock_while_closing(registered_catalog):
    """Other sessions stay usable while delete waits on an in-flight turn lock."""
    mgr = SessionManager(env=_env())
    active = mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)
    other = mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)

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
    created = mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)
    assert mgr.get(created.id) is created

    release.set()
    holder.join(timeout=2)
    deleter.join(timeout=2)
    assert delete_done.is_set()
    assert active.state.closed is True
