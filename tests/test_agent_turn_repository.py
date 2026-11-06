from datetime import datetime
from unittest.mock import MagicMock

import pytest

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.core.persistence import PostgresPersistence
from lakegen.core.persistence.repository.agent_turn_repository import (
    AgentTurnRepository,
)


def test_create_inserts_json_result() -> None:
    database = MagicMock(spec=PostgresPersistence)
    database.insert.return_value = {"id": 7}
    result = {"final_message": "done", "stop_reason": "completed"}

    turn_id = AgentTurnRepository(database).create(
        {
            "session_id": "session-1",
            "result": result,
        }
    )

    assert turn_id == 7
    table_name, row = database.insert.call_args.args
    assert table_name == "agent_turns"
    assert row["session_id"] == "session-1"
    assert row["result"].obj == result
    assert database.insert.call_args.kwargs == {
        "returning": "id",
        "connection": None,
    }


def test_create_requires_object_result() -> None:
    with pytest.raises(ValueError, match="result"):
        AgentTurnRepository(MagicMock(spec=PostgresPersistence)).create(
            {
                "session_id": "session-1",
                "result": "invalid",
            }
        )


def test_get_returns_turn() -> None:
    database = MagicMock(spec=PostgresPersistence)
    row = {
        "id": 1,
        "session_id": "session-1",
        "result": {},
        "created_at": datetime.now(),
    }
    database.fetch_one.return_value = row

    assert AgentTurnRepository(database).get(1) == row


def test_get_missing_raises_not_found() -> None:
    database = MagicMock(spec=PostgresPersistence)
    database.fetch_one.return_value = None

    with pytest.raises(BaseError) as exc_info:
        AgentTurnRepository(database).get("missing")

    assert exc_info.value.code == ErrorCode.NOT_FOUND


def test_list_is_session_scoped_and_paginated() -> None:
    database = MagicMock(spec=PostgresPersistence)
    database.fetch_all.return_value = []

    assert AgentTurnRepository(database).list("session-1", 10, 20) == []
    statement, parameters = database.fetch_all.call_args.args
    assert "WHERE session_id = %s" in statement
    assert "ORDER BY id DESC" in statement
    assert parameters == ("session-1", 10, 20)


def test_list_without_limit_omits_limit_clause() -> None:
    database = MagicMock(spec=PostgresPersistence)
    database.fetch_all.return_value = []

    assert AgentTurnRepository(database).list("session-1", 0, None) == []
    statement, parameters = database.fetch_all.call_args.args
    assert "LIMIT" not in statement
    assert parameters == ("session-1", 0)
