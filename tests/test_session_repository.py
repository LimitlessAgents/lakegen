from datetime import datetime
from unittest.mock import MagicMock

import pytest

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.core.persistence import PostgresPersistence
from lakegen.core.persistence.repository.base import Repository
from lakegen.core.persistence.repository.session_repository import SessionRepository


def test_repository_contract_is_abstract() -> None:
    with pytest.raises(TypeError):
        Repository()


def test_create_inserts_session() -> None:
    database = MagicMock(spec=PostgresPersistence)

    SessionRepository(database).create(
        {"id": "session-1", "owner_id": "user-1", "name": "Test"}
    )

    database.insert.assert_called_once_with(
        "sessions",
        {"id": "session-1", "owner_id": "user-1", "name": "Test"},
    )


def test_get_returns_session() -> None:
    database = MagicMock(spec=PostgresPersistence)
    row = {
        "id": "session-1",
        "owner_id": "user-1",
        "name": "Test",
        "created_at": datetime.now(),
    }
    database.fetch_one.return_value = row

    assert SessionRepository(database).get("session-1") == row
    statement, parameters = database.fetch_one.call_args.args
    assert "owner_id" in statement
    assert parameters == ("session-1",)


def test_get_missing_raises_not_found() -> None:
    database = MagicMock(spec=PostgresPersistence)
    database.fetch_one.return_value = None

    with pytest.raises(BaseError) as exc_info:
        SessionRepository(database).get("missing")

    assert exc_info.value.code == ErrorCode.NOT_FOUND


def test_exists_queries_by_id() -> None:
    database = MagicMock(spec=PostgresPersistence)
    database.fetch_one.return_value = {"found": 1}

    assert SessionRepository(database).exists("session-1") is True
    database.fetch_one.assert_called_once_with(
        "SELECT 1 AS found FROM sessions WHERE id = %s",
        ("session-1",),
    )


def test_list_is_owner_scoped_and_paginated() -> None:
    database = MagicMock(spec=PostgresPersistence)
    database.fetch_all.return_value = []

    assert (
        SessionRepository(database).list(
            "user-1",
            10,
            10,
        )
        == []
    )
    statement, parameters = database.fetch_all.call_args.args
    assert "WHERE owner_id = %s" in statement
    assert "ORDER BY created_at DESC, id DESC" in statement
    assert "LIMIT %s OFFSET %s" in statement
    assert parameters == ("user-1", 10, 10)


def _transaction_connection(database: MagicMock) -> MagicMock:
    connection = MagicMock()
    cursor = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    database.transaction.return_value.__enter__.return_value = connection
    return connection, cursor


def test_delete_removes_turns_then_session_in_one_transaction() -> None:
    database = MagicMock(spec=PostgresPersistence)
    connection, cursor = _transaction_connection(database)
    cursor.fetchall.return_value = [{"id": "session-1"}]

    SessionRepository(database).delete("session-1")

    database.transaction.assert_called_once()
    database.execute.assert_called_once_with(
        "DELETE FROM agent_turns WHERE session_id = ANY(%s)",
        (["session-1"],),
        connection=connection,
    )
    cursor.execute.assert_called_once_with(
        "DELETE FROM sessions WHERE id = ANY(%s) RETURNING id",
        (["session-1"],),
    )


def test_delete_accepts_multiple_ids_atomically() -> None:
    database = MagicMock(spec=PostgresPersistence)
    connection, cursor = _transaction_connection(database)
    cursor.fetchall.return_value = [
        {"id": "child"},
        {"id": "parent"},
    ]

    SessionRepository(database).delete(["parent", "child"])

    database.transaction.assert_called_once()
    database.execute.assert_called_once_with(
        "DELETE FROM agent_turns WHERE session_id = ANY(%s)",
        (["parent", "child"],),
        connection=connection,
    )


def test_delete_missing_raises_not_found() -> None:
    database = MagicMock(spec=PostgresPersistence)
    _connection, cursor = _transaction_connection(database)
    cursor.fetchall.return_value = []

    with pytest.raises(BaseError) as exc_info:
        SessionRepository(database).delete("missing")

    assert exc_info.value.code == ErrorCode.NOT_FOUND
    transaction = database.transaction.return_value
    assert transaction.__exit__.call_args.args[0] is BaseError


def test_delete_rolls_back_all_rows_when_any_id_is_missing() -> None:
    database = MagicMock(spec=PostgresPersistence)
    _connection, cursor = _transaction_connection(database)
    cursor.fetchall.return_value = [{"id": "existing"}]

    with pytest.raises(BaseError):
        SessionRepository(database).delete(["existing", "missing"])

    transaction = database.transaction.return_value
    assert transaction.__exit__.call_args.args[0] is BaseError
