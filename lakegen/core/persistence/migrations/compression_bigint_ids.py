"""One-time move from UUID turn/compression ids to ordered BIGINT ids.

The migration runs before schema creation and records itself in
``schema_migrations`` so the destructive column rewrites never run twice.
"""

from __future__ import annotations

import psycopg

from . import _markers

_MIGRATION_KEY = "001_compression_bigint_ids"


def migrate(connection: psycopg.Connection) -> None:
    """Move UUID turn/compression ids to ordered BIGINTs exactly once."""
    _markers.ensure_table(connection)
    if _markers.applied(connection, _MIGRATION_KEY):
        return

    agent_turn_id_type = _column_type(connection, "agent_turns", "id")
    old_compressions = _table_exists(connection, "compactions")
    new_compressions = _table_exists(connection, "compressions")
    if old_compressions and new_compressions:
        _drop_empty_compressions(connection)

    if agent_turn_id_type == "uuid":
        _migrate_uuid_ids(connection, compressions_exist=old_compressions)
    elif old_compressions and _column_type(connection, "compactions", "id") == "uuid":
        raise RuntimeError(
            "Cannot migrate compressions: agent_turns.id is already BIGINT "
            "but compactions.id is still UUID."
        )

    if old_compressions and _table_exists(connection, "compactions"):
        _rename_compressions(connection)

    _markers.mark(connection, _MIGRATION_KEY)


def _table_exists(connection: psycopg.Connection, table: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = current_schema() AND table_name = %s
        """,
        (table,),
    ).fetchone()
    return row is not None


def _column_type(
    connection: psycopg.Connection,
    table: str,
    column: str,
) -> str | None:
    row = connection.execute(
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
          AND column_name = %s
        """,
        (table, column),
    ).fetchone()
    return row[0] if row is not None else None


def _drop_empty_compressions(connection: psycopg.Connection) -> None:
    row = connection.execute("SELECT 1 FROM compressions LIMIT 1").fetchone()
    if row is not None:
        raise RuntimeError(
            "Both compactions and compressions tables contain data; "
            "cannot merge them automatically."
        )
    connection.execute("DROP TABLE compressions")


def _migrate_uuid_ids(
    connection: psycopg.Connection,
    *,
    compressions_exist: bool,
) -> None:
    # Preserve chronology for new ordered ids.
    connection.execute(
        """
        CREATE TEMP TABLE agent_turn_id_map ON COMMIT DROP AS
        SELECT id AS old_id,
               row_number() OVER (ORDER BY created_at, id) AS new_id
        FROM agent_turns
        """
    )
    connection.execute("ALTER TABLE agent_turns ADD COLUMN new_id BIGINT")
    connection.execute(
        """
        UPDATE agent_turns AS turn
        SET new_id = mapping.new_id
        FROM agent_turn_id_map AS mapping
        WHERE turn.id = mapping.old_id
        """
    )

    if compressions_exist:
        connection.execute("ALTER TABLE compactions ADD COLUMN new_id BIGINT")
        connection.execute(
            "ALTER TABLE compactions ADD COLUMN new_last_compressed_turn_id BIGINT"
        )
        connection.execute(
            """
            WITH ordered AS (
                SELECT id, row_number() OVER (ORDER BY created_at, id) AS new_id
                FROM compactions
            )
            UPDATE compactions AS compression
            SET new_id = ordered.new_id
            FROM ordered
            WHERE compression.id = ordered.id
            """
        )
        connection.execute(
            """
            UPDATE compactions AS compression
            SET new_last_compressed_turn_id = mapping.new_id
            FROM agent_turn_id_map AS mapping
            WHERE compression.last_compacted_turn_id = mapping.old_id
            """
        )
        connection.execute(
            "ALTER TABLE compactions DROP CONSTRAINT IF EXISTS "
            "compactions_last_compacted_turn_id_fkey"
        )
        connection.execute(
            "ALTER TABLE compactions DROP CONSTRAINT IF EXISTS "
            "compactions_session_id_fkey"
        )
        connection.execute(
            "ALTER TABLE compactions DROP CONSTRAINT IF EXISTS compactions_pkey"
        )

    connection.execute(
        "ALTER TABLE agent_turns DROP CONSTRAINT IF EXISTS agent_turns_session_id_fkey"
    )
    connection.execute(
        "ALTER TABLE agent_turns DROP CONSTRAINT IF EXISTS agent_turns_pkey"
    )

    if compressions_exist:
        connection.execute("ALTER TABLE compactions DROP COLUMN id")
        connection.execute("ALTER TABLE compactions DROP COLUMN last_compacted_turn_id")
        connection.execute("ALTER TABLE compactions RENAME COLUMN new_id TO id")
        connection.execute(
            "ALTER TABLE compactions RENAME COLUMN "
            "new_last_compressed_turn_id TO last_compressed_turn_id"
        )
        connection.execute("ALTER TABLE compactions RENAME TO compressions")
        connection.execute(
            "ALTER INDEX IF EXISTS compactions_session_created_at_idx "
            "RENAME TO compressions_session_created_at_idx"
        )

    connection.execute("ALTER TABLE agent_turns DROP COLUMN id")
    connection.execute("ALTER TABLE agent_turns RENAME COLUMN new_id TO id")
    connection.execute("ALTER TABLE agent_turns ALTER COLUMN id SET NOT NULL")
    connection.execute(
        "ALTER TABLE agent_turns ADD CONSTRAINT agent_turns_pkey PRIMARY KEY (id)"
    )
    connection.execute(
        "ALTER TABLE agent_turns ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY"
    )
    connection.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('agent_turns', 'id'),
            COALESCE(MAX(id), 1),
            MAX(id) IS NOT NULL
        )
        FROM agent_turns
        """
    )
    connection.execute(
        "ALTER TABLE agent_turns ADD CONSTRAINT agent_turns_session_id_fkey "
        "FOREIGN KEY (session_id) REFERENCES sessions(id)"
    )

    if compressions_exist:
        connection.execute("ALTER TABLE compressions ALTER COLUMN id SET NOT NULL")
        connection.execute(
            "ALTER TABLE compressions ALTER COLUMN last_compressed_turn_id SET NOT NULL"
        )
        connection.execute(
            "ALTER TABLE compressions ADD CONSTRAINT compressions_pkey PRIMARY KEY (id)"
        )
        connection.execute(
            "ALTER TABLE compressions ALTER COLUMN id "
            "ADD GENERATED BY DEFAULT AS IDENTITY"
        )
        connection.execute(
            """
            SELECT setval(
                pg_get_serial_sequence('compressions', 'id'),
                COALESCE(MAX(id), 1),
                MAX(id) IS NOT NULL
            )
            FROM compressions
            """
        )
        connection.execute(
            "ALTER TABLE compressions ADD CONSTRAINT "
            "compressions_session_id_fkey FOREIGN KEY (session_id) "
            "REFERENCES sessions(id) ON DELETE CASCADE"
        )
        connection.execute(
            "ALTER TABLE compressions ADD CONSTRAINT "
            "compressions_last_compressed_turn_id_fkey FOREIGN KEY "
            "(last_compressed_turn_id) REFERENCES agent_turns(id) "
            "ON DELETE CASCADE"
        )


def _rename_compressions(connection: psycopg.Connection) -> None:
    if _column_type(connection, "compactions", "last_compacted_turn_id") is not None:
        connection.execute(
            "ALTER TABLE compactions RENAME COLUMN "
            "last_compacted_turn_id TO last_compressed_turn_id"
        )
    connection.execute("ALTER TABLE compactions RENAME TO compressions")
    connection.execute(
        "ALTER INDEX IF EXISTS compactions_session_created_at_idx "
        "RENAME TO compressions_session_created_at_idx"
    )
    connection.execute(
        "ALTER SEQUENCE IF EXISTS compactions_id_seq RENAME TO compressions_id_seq"
    )
    for old, new in (
        ("compactions_pkey", "compressions_pkey"),
        ("compactions_session_id_fkey", "compressions_session_id_fkey"),
        (
            "compactions_last_compacted_turn_id_fkey",
            "compressions_last_compressed_turn_id_fkey",
        ),
    ):
        _rename_constraint(connection, "compressions", old, new)


def _rename_constraint(
    connection: psycopg.Connection,
    table: str,
    old: str,
    new: str,
) -> None:
    row = connection.execute(
        """
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = %s::regclass AND conname = %s
        """,
        (table, old),
    ).fetchone()
    if row is None:
        return
    connection.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {old} TO {new}")
