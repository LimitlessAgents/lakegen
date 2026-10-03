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
from lakegen.core.persistence import PostgresPersistence
from lakegen.session import Environment, SessionManager

from tests.conftest import open_session


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
    persistence = MagicMock(spec=PostgresPersistence)
    persistence.configured = False
    return replace(
        Environment.default(),
        catalog_service=catalogs,
        persistence=persistence,
        session_repository=MagicMock(),
        agent_turn_repository=MagicMock(),
    )


def test_create_get_list(registered_catalog):
    env = _env()
    mgr = SessionManager(env=env)
    a_id = mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)
    b_id = mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)
    a = mgr.get(a_id)
    b = mgr.get(b_id)
    created_at = datetime.now()
    env.session_repository.list.return_value = [
        {
            "id": b_id,
            "name": None,
            "catalog_name": registered_catalog,
            "created_at": created_at,
        },
        {
            "id": a_id,
            "name": "First",
            "catalog_name": registered_catalog,
            "created_at": created_at,
        },
    ]

    assert env.session_repository.create.call_count == 2
    env.session_repository.create.assert_any_call(
        {"id": a_id, "owner_id": _OWNER, "catalog_name": registered_catalog}
    )
    env.session_repository.create.assert_any_call(
        {"id": b_id, "owner_id": _OWNER, "catalog_name": registered_catalog}
    )
    assert mgr.get(a_id) is a
    assert mgr.get(b_id) is b
    listed = mgr.list(owner_id=_OWNER)
    assert [session.id for session in listed] == [b.id, a.id]
    assert all(session.catalog_name == registered_catalog for session in listed)
    env.session_repository.list.assert_called_once_with(_OWNER, 0, 10)
    assert a.state.catalog_name == registered_catalog
    env.persistence.ensure_schema.assert_not_called()


def test_list_does_not_block_create(registered_catalog):
    env = _env()
    mgr = SessionManager(env=env)
    query_started = threading.Event()
    release_query = threading.Event()

    def list_rows(*_args):
        query_started.set()
        assert release_query.wait(timeout=1)
        return []

    env.session_repository.list.side_effect = list_rows

    list_thread = threading.Thread(
        target=lambda: mgr.list(owner_id=_OWNER),
    )
    list_thread.start()
    assert query_started.wait(timeout=1)

    create_finished = threading.Event()

    def create_while_listing() -> None:
        mgr.create(
            _config(),
            owner_id=_OWNER,
            catalog_name=registered_catalog,
        )
        create_finished.set()

    create_thread = threading.Thread(target=create_while_listing)
    create_thread.start()
    assert create_finished.wait(timeout=1)

    release_query.set()
    list_thread.join(timeout=2)
    create_thread.join(timeout=2)


def test_list_uses_requested_offset():
    env = _env()
    mgr = SessionManager(env=env)
    env.session_repository.list.return_value = []

    assert mgr.list(owner_id=_OWNER, offset=10) == []
    env.session_repository.list.assert_called_once_with(_OWNER, 10, 10)


def test_list_turns_requires_persisted_owner():
    env = _env()
    mgr = SessionManager(env=env)
    env.session_repository.get.return_value = {
        "id": "session-1",
        "owner_id": _OWNER,
    }
    created_at = datetime.now()
    env.agent_turn_repository.list.return_value = [
        {"id": "turn-1", "created_at": created_at, "result": {}}
    ]

    turns = mgr.list_turns(
        "session-1",
        owner_id=_OWNER,
        offset=10,
        limit=20,
    )

    assert [turn.id for turn in turns] == ["turn-1"]
    env.agent_turn_repository.list.assert_called_once_with("session-1", 10, 20)


def test_list_turns_hides_another_owners_session():
    env = _env()
    mgr = SessionManager(env=env)
    env.session_repository.get.return_value = {
        "id": "session-1",
        "owner_id": "another-user",
    }

    with pytest.raises(BaseError) as exc_info:
        mgr.list_turns("session-1", owner_id=_OWNER)

    assert exc_info.value.code == ErrorCode.NOT_FOUND
    env.agent_turn_repository.list.assert_not_called()


def test_create_does_not_register_session_when_persistence_fails(
    registered_catalog,
):
    env = _env()
    env.session_repository.create.side_effect = RuntimeError("database unavailable")
    mgr = SessionManager(env=env)

    with pytest.raises(RuntimeError, match="database unavailable"):
        mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)

    env.session_repository.list.return_value = []
    assert mgr.list(owner_id=_OWNER) == []


def test_create_without_catalog(registered_catalog):
    mgr = SessionManager(env=_env())
    session = open_session(mgr, _config(), owner_id=_OWNER)
    assert session.state.catalog_name is None
    assert session.state.owner_id == _OWNER


def test_send_requires_catalog_on_first_turn(registered_catalog):
    mgr = SessionManager(env=_env())
    session = open_session(mgr, _config(), owner_id=_OWNER)
    with pytest.raises(BaseError, match="catalog_name is required"):
        session.send("hello")


def test_create_unknown_catalog_raises(registered_catalog):
    mgr = SessionManager(env=_env())
    with pytest.raises(BaseError, match="not registered"):
        mgr.create(_config(), owner_id=_OWNER, catalog_name="missing")


def test_spawn_inherits_catalog(registered_catalog):
    mgr = SessionManager(env=_env())
    parent = open_session(mgr, _config(), owner_id=_OWNER, catalog_name=registered_catalog)
    child = mgr.get(parent.spawn(_config(system_prompt="child")))

    assert child.parent_id == parent.id
    assert child.id in parent.state.children
    assert child.env is parent.env
    assert child.state.catalog_name == registered_catalog
    assert child.state.messages.messages == []


def test_delete_keeps_registry_when_persistence_fails(registered_catalog):
    env = _env()
    mgr = SessionManager(env=env)
    parent = open_session(mgr, _config(), owner_id=_OWNER, catalog_name=registered_catalog)
    child = mgr.get(parent.spawn(_config()))
    env.session_repository.delete.side_effect = RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        mgr.delete(child.id)

    assert mgr.get(child.id) is child
    assert mgr.get(parent.id) is parent
    assert child.state.closed is False


def test_delete_removes_only_requested_session(registered_catalog):
    env = _env()
    mgr = SessionManager(env=env)
    parent = open_session(mgr, _config(), owner_id=_OWNER, catalog_name=registered_catalog)
    child = mgr.get(parent.spawn(_config()))

    mgr.delete(child.id)

    env.session_repository.delete.assert_called_once_with(child.id)
    env.session_repository.get.side_effect = BaseError(
        ErrorCode.NOT_FOUND,
        "missing",
    )
    with pytest.raises(BaseError):
        mgr.get(child.id)
    assert mgr.get(parent.id) is parent


def test_get_missing_raises(registered_catalog):
    env = _env()
    env.session_repository.get.side_effect = BaseError(
        ErrorCode.NOT_FOUND,
        "missing",
    )
    mgr = SessionManager(env=env)
    with pytest.raises(BaseError):
        mgr.get("00000000-0000-0000-0000-000000000099")


def test_create_with_missing_parent_raises(registered_catalog):
    env = _env()
    env.session_repository.get.side_effect = BaseError(
        ErrorCode.NOT_FOUND,
        "missing parent",
    )
    mgr = SessionManager(env=env)
    with pytest.raises(BaseError):
        mgr.create(
            _config(),
            owner_id=_OWNER,
            catalog_name=registered_catalog,
            parent_id="00000000-0000-0000-0000-000000000042",
        )


def test_delete_closes_session_so_send_and_spawn_fail(registered_catalog):
    mgr = SessionManager(env=_env())
    session = open_session(mgr, _config(), owner_id=_OWNER, catalog_name=registered_catalog)

    mgr.delete(session.id)

    assert session.state.closed is True
    with pytest.raises(BaseError, match="closed"):
        session.send("hello")
    with pytest.raises(BaseError, match="closed"):
        session.spawn(_config())


def test_delete_closes_cached_session(registered_catalog):
    mgr = SessionManager(env=_env())
    parent = open_session(mgr, _config(), owner_id=_OWNER, catalog_name=registered_catalog)
    child = mgr.get(parent.spawn(_config()))

    mgr.delete(parent.id)

    assert parent.state.closed is True
    assert child.state.closed is False


def test_close_blocks_further_send_and_spawn(registered_catalog):
    mgr = SessionManager(env=_env())
    session = open_session(mgr, _config(), owner_id=_OWNER, catalog_name=registered_catalog)

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
    env = _env()
    mgr = SessionManager(env=env)
    active = open_session(mgr, _config(), owner_id=_OWNER, catalog_name=registered_catalog)
    other = open_session(mgr, _config(), owner_id=_OWNER, catalog_name=registered_catalog)

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
    created_id = mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)
    created = mgr.get(created_id)
    assert mgr.get(created_id) is created

    release.set()
    holder.join(timeout=2)
    deleter.join(timeout=2)
    assert delete_done.is_set()
    assert active.state.closed is True
    env.session_repository.get.side_effect = BaseError(
        ErrorCode.NOT_FOUND,
        "missing",
    )
    with pytest.raises(BaseError):
        mgr.get(active.id)


def test_delete_closes_evicted_session_when_pinned(registered_catalog):
    env = _env()
    mgr = SessionManager(env=env, cache_size=1)
    evicted = open_session(
        mgr,
        _config(),
        owner_id=_OWNER,
        catalog_name=registered_catalog,
    )
    mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)

    mgr.pin_session(evicted.id, evicted)
    mgr.delete(evicted.id)

    assert evicted.state.closed is True


def test_pin_session_rejects_deleted_session(registered_catalog):
    env = _env()
    mgr = SessionManager(env=env, cache_size=1)
    session = open_session(
        mgr,
        _config(),
        owner_id=_OWNER,
        catalog_name=registered_catalog,
    )
    session_id = session.id
    mgr.create(_config(), owner_id=_OWNER, catalog_name=registered_catalog)

    mgr.delete(session_id)
    env.session_repository.exists.return_value = False
    with pytest.raises(BaseError, match="not found"):
        mgr.pin_session(session_id, session)


def test_get_does_not_cache_session_deleted_during_hydrate(registered_catalog):
    env = _env()
    mgr = SessionManager(env=env)
    session_id = "00000000-0000-0000-0000-000000000001"
    created_at = datetime.now()
    env.session_repository.get.return_value = {
        "id": session_id,
        "owner_id": _OWNER,
        "catalog_name": registered_catalog,
        "created_at": created_at,
    }
    env.session_repository.exists.return_value = False

    with pytest.raises(BaseError, match="not found"):
        mgr.get(session_id)

    env.session_repository.exists.assert_called_once_with(session_id)


def test_get_concurrent_hydrate_returns_same_session(registered_catalog):
    env = _env()
    mgr = SessionManager(env=env)
    session_id = "00000000-0000-0000-0000-000000000001"
    created_at = datetime.now()
    env.session_repository.get.return_value = {
        "id": session_id,
        "owner_id": _OWNER,
        "catalog_name": registered_catalog,
        "created_at": created_at,
    }
    hydrate_calls = 0
    release_hydrate = threading.Event()

    def slow_list(*_args, **_kwargs):
        nonlocal hydrate_calls
        hydrate_calls += 1
        if hydrate_calls == 1:
            release_hydrate.wait(timeout=2)
        return []

    env.agent_turn_repository.list.side_effect = slow_list

    first: list = []

    def first_get() -> None:
        first.append(mgr.get(session_id))

    thread = threading.Thread(target=first_get)
    thread.start()
    time.sleep(0.05)
    second = mgr.get(session_id)
    release_hydrate.set()
    thread.join(timeout=2)

    assert hydrate_calls == 1
    assert first[0] is second


def test_get_hydrates_persisted_session(registered_catalog):
    env = _env()
    mgr = SessionManager(env=env, cache_size=8, hydrate_turn_limit=20)
    created_at = datetime.now()
    session_id = "00000000-0000-0000-0000-000000000001"
    env.session_repository.get.return_value = {
        "id": session_id,
        "owner_id": _OWNER,
        "catalog_name": registered_catalog,
        "created_at": created_at,
    }
    env.agent_turn_repository.list.return_value = [
        {
            "id": "turn-1",
            "created_at": created_at,
            "result": {
                "final_message": "ok",
                "stop_reason": "completed",
                "turn_messages": {
                    "messages": [
                        {
                            "role": "user",
                            "content": "hello",
                            "tool_calls": None,
                            "tool_call_id": None,
                            "tool_name": None,
                        }
                    ]
                },
            },
        }
    ]

    session = mgr.get(session_id)

    assert session.state.owner_id == _OWNER
    assert session.state.catalog_name == registered_catalog
    assert [message.content for message in session.state.messages.messages] == ["hello"]
    env.agent_turn_repository.list.assert_called_once_with(session_id, 0, 20)


def test_delete_blocks_spawn_and_send_before_deleting_rows(registered_catalog):
    env = _env()
    mgr = SessionManager(env=env)
    session = open_session(
        mgr,
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
    with pytest.raises(BaseError, match="not found"):
        session.send("hello")

    release_delete.set()
    deleter.join(timeout=2)
    assert not deleter.is_alive()
