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
    result = {"final_message": "done", "stop_reason": "completed"}

    AgentTurnRepository(database).create(
        {
            "id": "turn-1",
            "session_id": "session-1",
            "result": result,
        }
    )

    table_name, row = database.insert.call_args.args
    assert table_name == "agent_turns"
    assert row["id"] == "turn-1"
    assert row["session_id"] == "session-1"
    assert row["result"].obj == result


def test_create_requires_object_result() -> None:
    with pytest.raises(ValueError, match="result"):
        AgentTurnRepository(MagicMock(spec=PostgresPersistence)).create(
            {
                "id": "turn-1",
                "session_id": "session-1",
                "result": "invalid",
            }
        )


def test_get_returns_turn() -> None:
    database = MagicMock(spec=PostgresPersistence)
    row = {
        "id": "turn-1",
        "session_id": "session-1",
        "result": {},
        "created_at": datetime.now(),
    }
    database.fetch_one.return_value = row

    assert AgentTurnRepository(database).get("turn-1") == row


def test_get_missing_raises_not_found() -> None:
    database = MagicMock(spec=PostgresPersistence)
    database.fetch_one.return_value = None

    with pytest.raises(BaseError) as exc_info:
        AgentTurnRepository(database).get("missing")

    assert exc_info.value.code == ErrorCode.NOT_FOUND
