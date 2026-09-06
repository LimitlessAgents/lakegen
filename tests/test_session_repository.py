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

    SessionRepository(database).create({"id": "session-1", "name": "Test"})

    database.insert.assert_called_once_with(
        "sessions",
        {"id": "session-1", "name": "Test"},
    )


def test_get_returns_session() -> None:
    database = MagicMock(spec=PostgresPersistence)
    row = {
        "id": "session-1",
        "name": "Test",
        "created_at": datetime.now(),
    }
    database.fetch_one.return_value = row

    assert SessionRepository(database).get("session-1") == row


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


def test_delete_missing_raises_not_found() -> None:
    database = MagicMock(spec=PostgresPersistence)
    database.fetch_one.return_value = None

    with pytest.raises(BaseError) as exc_info:
        SessionRepository(database).delete("missing")

    assert exc_info.value.code == ErrorCode.NOT_FOUND
