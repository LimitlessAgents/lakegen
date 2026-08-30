import os
from collections.abc import Mapping
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


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

    def ensure_schema(self) -> None:
        """Apply ``schema.sql`` once. Call at process startup, not per write."""
        if not self.url:
            raise RuntimeError(
                "PostgreSQL persistence is not configured; set LAKEGEN_DATABASE_URL."
            )

        statements = [
            statement.strip()
            for statement in _SCHEMA_PATH.read_text().split(";")
            if statement.strip()
        ]
        with psycopg.connect(self.url) as connection:
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

    def _store(
        self,
        table_name: str,
        data: Mapping[str, object],
    ) -> None:
        if not self.url:
            raise RuntimeError(
                "PostgreSQL persistence is not configured; set LAKEGEN_DATABASE_URL."
            )
        if not table_name:
            raise ValueError("table_name must not be empty.")
        if not data:
            raise ValueError("data must contain at least one column.")

        columns = tuple(data)
        statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(table_name),
            sql.SQL(", ").join(sql.Identifier(column) for column in columns),
            sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        )

        with psycopg.connect(self.url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, tuple(data[column] for column in columns))


persistence = PostgresPersistence()