"""Bookkeeping shared by the one-time persistence migrations."""

from __future__ import annotations

import psycopg


def ensure_table(connection: psycopg.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            key TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def applied(connection: psycopg.Connection, key: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM schema_migrations WHERE key = %s",
        (key,),
    ).fetchone()
    return row is not None


def mark(connection: psycopg.Connection, key: str) -> None:
    connection.execute(
        "INSERT INTO schema_migrations (key) VALUES (%s)",
        (key,),
    )
