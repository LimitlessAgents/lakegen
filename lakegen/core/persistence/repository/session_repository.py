from collections.abc import Mapping, Sequence

from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.core.persistence import PostgresPersistence, persistence
from lakegen.core.persistence.repository.base import Repository


class SessionRepository(Repository):

    def create(self, data: Mapping[str, object]) -> None:
        payload = dict(data)
        session_id = self._required_string(payload, "id")
        row = {
            "id": session_id,
            "owner_id": self._required_string(payload, "owner_id"),
            "name": payload.get("name"),
        }

        try:
            self._database.insert("sessions", row)
        except UniqueViolation as error:
            raise BaseError(
                ErrorCode.ALREADY_EXISTS,
                f"Session {session_id!r} already exists.",
            ) from error

    def get(self, identifier: str) -> dict[str, object]:
        row = self._database.fetch_one(
            "SELECT id, name, created_at FROM sessions WHERE id = %s",
            (identifier,),
        )
        if row is None:
            self._raise_not_found(identifier)
        return row

    def list_all(
        self,
        *,
        owner_id: str,
        limit: int,
        offset: int,
    ) -> list[dict[str, object]]:
        return self._database.fetch_all(
            """
            SELECT id, name, created_at
            FROM sessions
            WHERE owner_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s OFFSET %s
            """,
            (owner_id, limit, offset),
        )

    def exists(self, identifier: str) -> bool:
        if not identifier:
            return False
        return (
            self._database.fetch_one(
                "SELECT 1 AS found FROM sessions WHERE id = %s",
                (identifier,),
            )
            is not None
        )

    def delete(self, identifiers: str | Sequence[str]) -> None:
        """Delete turns and session rows for one or more ids in one transaction."""
        ids = [identifiers] if isinstance(identifiers, str) else list(identifiers)
        if not ids:
            return

        with self._database.transaction() as connection:
            self._database.execute(
                "DELETE FROM agent_turns WHERE session_id = ANY(%s)",
                (ids,),
                connection=connection,
            )
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    "DELETE FROM sessions WHERE id = ANY(%s) RETURNING id",
                    (ids,),
                )
                deleted = {str(row["id"]) for row in cursor.fetchall()}

            missing = set(ids) - deleted
            if missing:
                self._raise_not_found(next(iter(missing)))

    @staticmethod
    def _raise_not_found(identifier: str) -> None:
        raise BaseError(
            ErrorCode.NOT_FOUND,
            f"Session {identifier!r} not found.",
        )


session_repository = SessionRepository()