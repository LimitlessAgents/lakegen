from unittest.mock import MagicMock

import pytest

from lakegen.core.persistence import PostgresPersistence


def test_store_uses_parameterized_insert(mocker) -> None:
    connection = MagicMock()
    cursor = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connect = mocker.patch(
        "lakegen.core.persistence.postgres.psycopg.connect"
    )
    connect.return_value.__enter__.return_value = connection

    persistence = PostgresPersistence("postgresql://localhost/lakegen")
    persistence._store("messages", {"session_id": "abc", "content": "hello"})

    connect.assert_called_once_with("postgresql://localhost/lakegen")
    statement, values = cursor.execute.call_args.args
    assert statement.as_string() == (
        'INSERT INTO "messages" ("session_id", "content") VALUES (%s, %s)'
    )
    assert values == ("abc", "hello")


def test_store_turn_wraps_result_as_jsonb(mocker) -> None:
    persistence = PostgresPersistence("postgresql://localhost/lakegen")
    store = mocker.patch.object(persistence, "_store")

    persistence.store_turn(
        session_id="session-1",
        turn_id="turn-1",
        result={"final_message": "hello", "stop_reason": "completed"},
    )

    table_name, data = store.call_args.args
    assert table_name == "agent_turns"
    assert data["id"] == "turn-1"
    assert data["session_id"] == "session-1"
    assert data["result"].obj == {
        "final_message": "hello",
        "stop_reason": "completed",
    }


def test_ensure_schema_applies_schema_sql(mocker) -> None:
    connection = MagicMock()
    connect = mocker.patch(
        "lakegen.core.persistence.postgres.psycopg.connect"
    )
    connect.return_value.__enter__.return_value = connection

    PostgresPersistence("postgresql://localhost/lakegen").ensure_schema()

    connect.assert_called_once_with("postgresql://localhost/lakegen")
    statements = [call.args[0] for call in connection.execute.call_args_list]
    assert any("CREATE TABLE IF NOT EXISTS agent_turns" in s for s in statements)
    assert any(
        "CREATE INDEX IF NOT EXISTS agent_turns_session_id_created_at_idx" in s
        for s in statements
    )


def test_ensure_schema_requires_configuration(monkeypatch) -> None:
    monkeypatch.delenv("LAKEGEN_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="LAKEGEN_DATABASE_URL"):
        PostgresPersistence().ensure_schema()


def test_store_requires_configuration(monkeypatch) -> None:
    monkeypatch.delenv("LAKEGEN_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="LAKEGEN_DATABASE_URL"):
        PostgresPersistence()._store("messages", {"content": "hello"})


@pytest.mark.parametrize(
    ("table_name", "data", "message"),
    [
        ("", {"content": "hello"}, "table_name"),
        ("messages", {}, "at least one column"),
    ],
)
def test_store_validates_input(table_name, data, message) -> None:
    with pytest.raises(ValueError, match=message):
        PostgresPersistence("postgresql://localhost/lakegen")._store(
            table_name,
            data,
        )
