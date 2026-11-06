from datetime import datetime
from unittest.mock import MagicMock

import pytest

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.core.persistence import PostgresPersistence
from lakegen.core.persistence.repository.compression_repository import (
    CompressionRepository,
)


def test_create_inserts_compression() -> None:
    database = MagicMock(spec=PostgresPersistence)
    database.insert.return_value = {"id": 3}

    compression_id = CompressionRepository(database).create(
        {
            "session_id": "session-1",
            "data": "Compressed context:\nsummary",
            "last_compressed_turn_id": 5,
        }
    )

    assert compression_id == 3
    database.insert.assert_called_once_with(
        "compressions",
        {
            "data": "Compressed context:\nsummary",
            "session_id": "session-1",
            "last_compressed_turn_id": 5,
        },
        returning="id",
        connection=None,
    )


def test_get_returns_compression() -> None:
    database = MagicMock(spec=PostgresPersistence)
    row = {
        "id": 3,
        "session_id": "session-1",
        "data": "Compressed context:\nsummary",
        "last_compressed_turn_id": 5,
        "created_at": datetime.now(),
    }
    database.fetch_one.return_value = row

    assert CompressionRepository(database).get(3) == row


def test_get_missing_raises_not_found() -> None:
    database = MagicMock(spec=PostgresPersistence)
    database.fetch_one.return_value = None

    with pytest.raises(BaseError) as exc_info:
        CompressionRepository(database).get("missing")

    assert exc_info.value.code == ErrorCode.NOT_FOUND


def test_list_is_session_scoped_and_paginated() -> None:
    database = MagicMock(spec=PostgresPersistence)
    database.fetch_all.return_value = []

    assert CompressionRepository(database).list("session-1", 10, 20) == []
    statement, parameters = database.fetch_all.call_args.args
    assert "WHERE session_id = %s" in statement
    assert "ORDER BY id DESC" in statement
    assert parameters == ("session-1", 10, 20)
