from unittest.mock import MagicMock

from lakegen.core.persistence.migrations import (
    compression_bigint_ids as bigint_migration,
)
from lakegen.core.persistence.migrations import retire_compressions as retire_migration


def _markers(applied: bool) -> MagicMock:
    markers = MagicMock()
    markers.applied.return_value = applied
    return markers


def test_bigint_migration_is_skipped_after_first_run(monkeypatch) -> None:
    connection = MagicMock()
    markers = _markers(applied=True)
    column_type = MagicMock()
    table_exists = MagicMock()
    migrate_uuid_ids = MagicMock()
    rename_compressions = MagicMock()
    monkeypatch.setattr(bigint_migration, "_markers", markers)
    monkeypatch.setattr(bigint_migration, "_column_type", column_type)
    monkeypatch.setattr(bigint_migration, "_table_exists", table_exists)
    monkeypatch.setattr(bigint_migration, "_migrate_uuid_ids", migrate_uuid_ids)
    monkeypatch.setattr(bigint_migration, "_rename_compressions", rename_compressions)

    bigint_migration.migrate(connection)

    markers.ensure_table.assert_called_once_with(connection)
    markers.applied.assert_called_once_with(
        connection,
        bigint_migration._MIGRATION_KEY,
    )
    markers.mark.assert_not_called()
    column_type.assert_not_called()
    table_exists.assert_not_called()
    migrate_uuid_ids.assert_not_called()
    rename_compressions.assert_not_called()


def test_bigint_migration_rewrites_uuid_ids_and_does_not_rename_twice(
    monkeypatch,
) -> None:
    connection = MagicMock()
    markers = _markers(applied=False)
    tables = {"compactions"}
    monkeypatch.setattr(bigint_migration, "_markers", markers)
    monkeypatch.setattr(
        bigint_migration,
        "_column_type",
        MagicMock(
            side_effect=lambda conn, table, column: (
                "uuid" if (table, column) == ("agent_turns", "id") else None
            )
        ),
    )
    monkeypatch.setattr(
        bigint_migration,
        "_table_exists",
        MagicMock(side_effect=lambda conn, table: table in tables),
    )
    migrate_uuid_ids = MagicMock(
        side_effect=lambda *args, **kwargs: tables.remove("compactions")
    )
    rename_compressions = MagicMock()
    monkeypatch.setattr(bigint_migration, "_migrate_uuid_ids", migrate_uuid_ids)
    monkeypatch.setattr(bigint_migration, "_rename_compressions", rename_compressions)

    bigint_migration.migrate(connection)

    migrate_uuid_ids.assert_called_once_with(connection, compressions_exist=True)
    rename_compressions.assert_not_called()
    markers.mark.assert_called_once_with(
        connection,
        bigint_migration._MIGRATION_KEY,
    )


def test_bigint_migration_renames_intermediate_compactions_table(
    monkeypatch,
) -> None:
    connection = MagicMock()
    markers = _markers(applied=False)
    monkeypatch.setattr(bigint_migration, "_markers", markers)
    monkeypatch.setattr(
        bigint_migration,
        "_column_type",
        MagicMock(
            side_effect=lambda conn, table, column: (
                "bigint" if (table, column) == ("agent_turns", "id") else None
            )
        ),
    )
    monkeypatch.setattr(
        bigint_migration,
        "_table_exists",
        MagicMock(side_effect=lambda conn, table: table == "compactions"),
    )
    migrate_uuid_ids = MagicMock()
    rename_compressions = MagicMock()
    monkeypatch.setattr(bigint_migration, "_migrate_uuid_ids", migrate_uuid_ids)
    monkeypatch.setattr(bigint_migration, "_rename_compressions", rename_compressions)

    bigint_migration.migrate(connection)

    migrate_uuid_ids.assert_not_called()
    rename_compressions.assert_called_once_with(connection)
    markers.mark.assert_called_once_with(
        connection,
        bigint_migration._MIGRATION_KEY,
    )


def test_retire_compressions_is_skipped_after_first_run(monkeypatch) -> None:
    connection = MagicMock()
    markers = _markers(applied=True)
    monkeypatch.setattr(retire_migration, "_markers", markers)

    retire_migration.migrate(connection)

    markers.ensure_table.assert_called_once_with(connection)
    markers.applied.assert_called_once_with(
        connection,
        retire_migration._MIGRATION_KEY,
    )
    markers.mark.assert_not_called()
    connection.execute.assert_not_called()


def test_retire_compressions_backfills_and_drops_the_legacy_table(
    monkeypatch,
) -> None:
    connection = MagicMock()
    markers = _markers(applied=False)
    monkeypatch.setattr(retire_migration, "_markers", markers)
    monkeypatch.setattr(retire_migration, "_table_exists", MagicMock(return_value=True))

    retire_migration.migrate(connection)

    statements = [call.args[0] for call in connection.execute.call_args_list]
    assert any("ALTER TABLE agent_turns" in statement for statement in statements)
    assert any("UPDATE agent_turns" in statement for statement in statements)
    assert "DROP TABLE compressions" in statements
    markers.mark.assert_called_once_with(
        connection,
        retire_migration._MIGRATION_KEY,
    )


def test_retire_compressions_marks_without_a_legacy_table(monkeypatch) -> None:
    connection = MagicMock()
    markers = _markers(applied=False)
    monkeypatch.setattr(retire_migration, "_markers", markers)
    monkeypatch.setattr(retire_migration, "_table_exists", MagicMock(return_value=False))

    retire_migration.migrate(connection)

    connection.execute.assert_not_called()
    markers.mark.assert_called_once_with(
        connection,
        retire_migration._MIGRATION_KEY,
    )
