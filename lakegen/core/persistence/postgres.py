import os
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

_SCHEMA_PATH = Path(__file__).with_name("schema")


class PostgresPersistence:
    def __init__(
        self,
        host_url: str | None = None,
    ) -> None:
        self._host_url = host_url

    @property
    def url(self) -> str | None:
        return self._host_url or os.getenv("LAKEGEN_DATABASE_URL")

    @property
    def configured(self) -> bool:
        return bool(self.url)

    @contextmanager
    def transaction(self) -> Iterator[psycopg.Connection]:
        """Yield one connection that commits or rolls back as a unit."""
        if not self.url:
            raise RuntimeError(
                "PostgreSQL persistence is not configured; set LAKEGEN_DATABASE_URL."
            )

        with psycopg.connect(self.url) as connection:
            yield connection

    def ensure_schema(self) -> None:
        """Apply schema files in order. Call at process startup, not per write."""
        with self.transaction() as connection:
            for schema_file in sorted(_SCHEMA_PATH.glob("*.sql")):
                statements = [
                    statement.strip()
                    for statement in schema_file.read_text().split(";")
                    if statement.strip()
                ]
                for statement in statements:
                    connection.execute(statement)

    def store_turn(
        self,
        session_id: str,
        turn_id: str,
        result: Mapping[str, object],
    ) -> None:
        self._store(
            "agent_turns",
            {
                "id": turn_id,
                "session_id": session_id,
                "result": Jsonb(dict(result)),
            },
        )

    def insert(
        self,
        table_name: str,
        data: Mapping[str, object],
        *,
        connection: psycopg.Connection | None = None,
    ) -> None:
        """Insert one row, optionally as part of an existing transaction."""
        if not table_name:
            raise ValueError("table_name must not be empty.")
        if not data:
            raise ValueError("data must contain at least one column.")

        if connection is None:
            with self.transaction() as transaction:
                self.insert(table_name, data, connection=transaction)
            return

        columns = tuple(data)
        statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(table_name),
            sql.SQL(", ").join(sql.Identifier(column) for column in columns),
            sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        )

        with connection.cursor() as cursor:
            cursor.execute(statement, tuple(data[column] for column in columns))

    def execute(
        self,
        statement: str,
        parameters: Sequence[object] = (),
        *,
        connection: psycopg.Connection | None = None,
    ) -> None:
        """Execute a parameterized statement."""
        if connection is None:
            with self.transaction() as transaction:
                self.execute(statement, parameters, connection=transaction)
            return

        connection.execute(statement, parameters)

    def fetch_one(
        self,
        statement: str,
        parameters: Sequence[object] = (),
    ) -> dict[str, object] | None:
        """Return one row as a dictionary."""
        with self.transaction() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(statement, parameters)
                return cursor.fetchone()

    def fetch_all(
        self,
        statement: str,
        parameters: Sequence[object] = (),
    ) -> list[dict[str, object]]:
        """Return all rows as dictionaries."""
        with self.transaction() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(statement, parameters)
                return cursor.fetchall()

    def _store(
        self,
        table_name: str,
        data: Mapping[str, object],
    ) -> None:
        self.insert(table_name, data)


persistence = PostgresPersistence()