from unittest.mock import MagicMock

from lakegen.core.persistence.migrations import compression_bigint_ids as migration


def _connection(marker_present: bool) -> MagicMock:
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = (
        (1,) if marker_present else None
    )
    return connection


def test_migration_is_skipped_after_first_run(monkeypatch) -> None:
    connection = _connection(marker_present=True)
    ensure_marker = MagicMock()
    column_type = MagicMock()
    table_exists = MagicMock()
    migrate_uuid_ids = MagicMock()
    rename_compressions = MagicMock()
    monkeypatch.setattr(migration, "_ensure_marker_table", ensure_marker)
    monkeypatch.setattr(migration, "_column_type", column_type)
    monkeypatch.setattr(migration, "_table_exists", table_exists)
    monkeypatch.setattr(migration, "_migrate_uuid_ids", migrate_uuid_ids)
    monkeypatch.setattr(migration, "_rename_compressions", rename_compressions)

    migration.migrate(connection)

    ensure_marker.assert_called_once_with(connection)
    column_type.assert_not_called()
    table_exists.assert_not_called()
    migrate_uuid_ids.assert_not_called()
    rename_compressions.assert_not_called()
    assert connection.execute.call_count == 1


def test_migration_rewrites_uuid_ids_and_does_not_rename_twice(monkeypatch) -> None:
    connection = _connection(marker_present=False)
    tables = {"compactions"}
    monkeypatch.setattr(migration, "_ensure_marker_table", MagicMock())
    monkeypatch.setattr(
        migration,
        "_column_type",
        MagicMock(
            side_effect=lambda conn, table, column: (
                "uuid" if (table, column) == ("agent_turns", "id") else None
            )
        ),
    )
    monkeypatch.setattr(
        migration,
        "_table_exists",
        MagicMock(side_effect=lambda conn, table: table in tables),
    )
    migrate_uuid_ids = MagicMock(
        side_effect=lambda *args, **kwargs: tables.remove("compactions")
    )
    rename_compressions = MagicMock()
    monkeypatch.setattr(migration, "_migrate_uuid_ids", migrate_uuid_ids)
    monkeypatch.setattr(migration, "_rename_compressions", rename_compressions)

    migration.migrate(connection)

    migrate_uuid_ids.assert_called_once_with(connection, compressions_exist=True)
    rename_compressions.assert_not_called()
    assert "INSERT INTO schema_migrations" in connection.execute.call_args.args[0]


def test_migration_renames_intermediate_compactions_table(monkeypatch) -> None:
    connection = _connection(marker_present=False)
    monkeypatch.setattr(migration, "_ensure_marker_table", MagicMock())
    monkeypatch.setattr(
        migration,
        "_column_type",
        MagicMock(
            side_effect=lambda conn, table, column: (
                "bigint" if (table, column) == ("agent_turns", "id") else None
            )
        ),
    )
    monkeypatch.setattr(
        migration,
        "_table_exists",
        MagicMock(side_effect=lambda conn, table: table == "compactions"),
    )
    migrate_uuid_ids = MagicMock()
    rename_compressions = MagicMock()
    monkeypatch.setattr(migration, "_migrate_uuid_ids", migrate_uuid_ids)
    monkeypatch.setattr(migration, "_rename_compressions", rename_compressions)

    migration.migrate(connection)

    migrate_uuid_ids.assert_not_called()
    rename_compressions.assert_called_once_with(connection)
    assert "INSERT INTO schema_migrations" in connection.execute.call_args.args[0]
