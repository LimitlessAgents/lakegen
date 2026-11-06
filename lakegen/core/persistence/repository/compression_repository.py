from __future__ import annotations

from collections.abc import Mapping

from psycopg import Connection

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.core.persistence.repository.base import Repository


class CompressionRepository(Repository):
    def create(
        self,
        data: Mapping[str, object],
        *,
        connection: Connection | None = None,
    ) -> int:
        payload = dict(data)
        row = self._database.insert(
            "compressions",
            {
                "data": self._required_string(payload, "data"),
                "session_id": self._required_string(payload, "session_id"),
                "last_compressed_turn_id": self._required_int(
                    payload,
                    "last_compressed_turn_id",
                ),
            },
            returning="id",
            connection=connection,
        )
        if row is None:
            raise RuntimeError("Compression insert did not return an id.")
        return int(row["id"])

    def get(self, identifier: int) -> dict[str, object]:
        row = self._database.fetch_one(
            """
            SELECT id, session_id, data,
                   last_compressed_turn_id, created_at
            FROM compressions
            WHERE id = %s
            """,
            (identifier,),
        )
        if row is None:
            self._raise_not_found(identifier)
        return row

    def list(
        self,
        identifier: str,
        offset: int = 0,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        return self._database.fetch_all(
            """
            SELECT id, session_id, data,
                   last_compressed_turn_id, created_at
            FROM compressions
            WHERE session_id = %s
            ORDER BY id DESC
            OFFSET %s
            LIMIT %s
            """,
            (identifier, offset, limit),
        )

    def exists(self, identifier: int) -> bool:
        return (
            self._database.fetch_one(
                "SELECT 1 AS found FROM compressions WHERE id = %s",
                (identifier,),
            )
            is not None
        )

    def delete(self, identifier: int) -> None:
        row = self._database.fetch_one(
            "DELETE FROM compressions WHERE id = %s RETURNING id",
            (identifier,),
        )
        if row is None:
            self._raise_not_found(identifier)

    @staticmethod
    def _raise_not_found(identifier: object) -> None:
        raise BaseError(
            ErrorCode.NOT_FOUND,
            f"Compression {identifier!r} not found.",
        )


compression_repository = CompressionRepository()
