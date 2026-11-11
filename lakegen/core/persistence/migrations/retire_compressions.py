"""One-time move of legacy compaction summaries onto agent turns.

History summaries now live on ``agent_turns``; the ``compressions`` table is
dead. This migration copies the latest legacy compaction for each session onto
its turn, then drops the table.

It runs before the schema files, so on an old database it adds the destination
columns first. On a fresh database there is no legacy table and this is a no-op.
"""

from __future__ import annotations

import psycopg

from . import _markers

_MIGRATION_KEY = "002_retire_compressions"

_SUMMARY_COLUMNS = """
ALTER TABLE agent_turns
    ADD COLUMN IF NOT EXISTS summary TEXT,
    ADD COLUMN IF NOT EXISTS summary_kind TEXT,
    ADD COLUMN IF NOT EXISTS context_tokens INTEGER,
    ADD COLUMN IF NOT EXISTS context_source TEXT
"""

# The guard keeps newer summaries from being overwritten. The legacy in-memory
# tail is not migrated: legacy turns are stored uncompressed and replay as
# stored after the summary.
_BACKFILL = """
UPDATE agent_turns AS turn
SET summary = latest.data,
    summary_kind = 'history',
    context_source = 'legacy'
FROM (
    SELECT DISTINCT ON (session_id)
           session_id, last_compressed_turn_id, data
    FROM compressions
    ORDER BY session_id, id DESC
) AS latest
WHERE turn.id = latest.last_compressed_turn_id
  AND turn.summary IS NULL
"""


def migrate(connection: psycopg.Connection) -> None:
    """Copy legacy summaries and drop ``compressions`` exactly once."""
    _markers.ensure_table(connection)
    if _markers.applied(connection, _MIGRATION_KEY):
        return

    if _table_exists(connection, "compressions"):
        connection.execute(_SUMMARY_COLUMNS)
        connection.execute(_BACKFILL)
        connection.execute("DROP TABLE compressions")

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
