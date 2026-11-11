"""One-time persistence migrations, applied before the schema files."""

from __future__ import annotations

import psycopg

from . import compression_bigint_ids, retire_compressions


def migrate(connection: psycopg.Connection) -> None:
    compression_bigint_ids.migrate(connection)
    retire_compressions.migrate(connection)


__all__ = ["migrate"]
