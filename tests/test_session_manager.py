"""Tests for lakegen.session.manager.SessionManager."""

import threading
import time
from dataclasses import replace
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from lakegen.agent import AgentConfig
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.session import Environment, SessionManager


@pytest.fixture()
def registered_catalog():
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
    catalogs = MagicMock()

    def require(name):
        if name == "missing":
            raise BaseError(ErrorCode.NOT_FOUND, "Catalog is not registered.")

    catalogs.require.side_effect = require
    return replace(
        Environment.default(),
        catalog_service=catalogs,
        persistence=MagicMock(),
        session_repository=MagicMock(),
        agent_turn_repository=MagicMock(),
    )


def test_create_get_list(registered_catalog):
    env = _env()
    mgr = SessionManager(env=env)
    a = mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)
    b = mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)
    created_at = datetime.now()
    env.session_repository.list_all.return_value = [
        {"id": b.id, "name": None, "created_at": created_at},
        {"id": a.id, "name": "First", "created_at": created_at},
    ]

    assert env.session_repository.create.call_count == 2
    env.session_repository.create.assert_any_call(
        {"id": a.id, "owner_id": _OWNER}
    )
    env.session_repository.create.assert_any_call(
        {"id": b.id, "owner_id": _OWNER}
    )
    assert mgr.get(a.id) is a
    assert mgr.get(b.id) is b
    listed = mgr.list(owner_id=_OWNER)
    assert [session.id for session in listed] == [b.id, a.id]
    assert all(session.live for session in listed)
    env.session_repository.list_all.assert_called_once_with(
        owner_id=_OWNER,
        limit=10,
        offset=0,
    )
    assert a.state.catalog_name == registered_catalog
    env.persistence.ensure_schema.assert_called_once()


def test_list_holds_manager_lock_while_querying_persisted_rows():
    env = _env()
    mgr = SessionManager(env=env)
    query_started = threading.Event()
    release_query = threading.Event()

    def list_all(**_kwargs):
        query_started.set()
        assert release_query.wait(timeout=1)
        return []

    env.session_repository.list_all.side_effect = list_all

    list_thread = threading.Thread(
        target=lambda: mgr.list(owner_id=_OWNER),
    )
    list_thread.start()
    assert query_started.wait(timeout=1)

    create_finished = threading.Event()

    def create_while_listing() -> None:
        mgr.create(_config(), owner_id=_OWNER)
        create_finished.set()

    create_thread = threading.Thread(target=create_while_listing)
    create_thread.start()
    time.sleep(0.05)
    assert not create_finished.is_set()

    release_query.set()
    list_thread.join(timeout=2)
    create_thread.join(timeout=2)
    assert create_finished.is_set()


def test_list_uses_requested_offset():
    env = _env()
    mgr = SessionManager(env=env)
    env.session_repository.list_all.return_value = []

    assert mgr.list(owner_id=_OWNER, offset=10) == []
    env.session_repository.list_all.assert_called_once_with(
        owner_id=_OWNER,
        limit=10,
        offset=10,
    )


def test_create_does_not_register_session_when_persistence_fails(
    registered_catalog,
):
    env = _env()
    env.session_repository.create.side_effect = RuntimeError("database unavailable")
    mgr = SessionManager(env=env)

    with pytest.raises(RuntimeError, match="database unavailable"):
        mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)

    env.session_repository.list_all.return_value = []
    assert mgr.list(owner_id=_OWNER) == []


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


def test_delete_keeps_registry_when_persistence_fails(registered_catalog):
    env = _env()
    mgr = SessionManager(env=env)
    parent = mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)
    child = parent.spawn(_config())
    env.session_repository.delete.side_effect = RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        mgr.delete(child.id)

    assert mgr.get(child.id) is child
    assert mgr.get(parent.id) is parent
    assert child.state.closed is False


def test_delete_removes_children_and_unlinks_parent(registered_catalog):
    env = _env()
    mgr = SessionManager(env=env)
    parent = mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)
    child = parent.spawn(_config())
    grandchild = child.spawn(_config())

    mgr.delete(child.id)

    env.session_repository.delete.assert_called_once()
    deleted_ids = set(env.session_repository.delete.call_args.args[0])
    assert deleted_ids == {child.id, grandchild.id}
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


def test_delete_quiesces_session_without_blocking_unrelated_sessions(
    registered_catalog,
):
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

    time.sleep(0.05)
    assert not delete_done.is_set()
    assert active.state.closed is False
    assert mgr.get(active.id) is active
    assert mgr.get(other.id) is other
    created = mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)
    assert mgr.get(created.id) is created

    release.set()
    holder.join(timeout=2)
    deleter.join(timeout=2)
    assert delete_done.is_set()
    assert active.state.closed is True
    with pytest.raises(BaseError):
        mgr.get(active.id)


def test_delete_blocks_spawn_and_send_before_deleting_rows(registered_catalog):
    env = _env()
    mgr = SessionManager(env=env)
    session = mgr.create(
        _config(),
        owner_id=_OWNER,
        catalog_name=registered_catalog,
    )
    deleting_rows = threading.Event()
    release_delete = threading.Event()

    def delete_rows(_ids) -> None:
        deleting_rows.set()
        assert release_delete.wait(timeout=2)

    env.session_repository.delete.side_effect = delete_rows
    deleter = threading.Thread(target=lambda: mgr.delete(session.id))
    deleter.start()
    assert deleting_rows.wait(timeout=1)

    with pytest.raises(BaseError, match="closed"):
        session.spawn(_config())
    with pytest.raises(BaseError, match="closed"):
        session.send("hello")

    release_delete.set()
    deleter.join(timeout=2)
    assert not deleter.is_alive()
