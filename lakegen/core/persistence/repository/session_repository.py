from collections.abc import Mapping

from psycopg.errors import UniqueViolation

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

    def delete(self, identifier: str) -> None:
        self._database.execute(
            "DELETE FROM agent_turns WHERE session_id = %s",
            (identifier,),
        )
        row = self._database.fetch_one(
            "DELETE FROM sessions WHERE id = %s RETURNING id",
            (identifier,),
        )
        if row is None:
            self._raise_not_found(identifier)

    @staticmethod
    def _raise_not_found(identifier: str) -> None:
        raise BaseError(
            ErrorCode.NOT_FOUND,
            f"Session {identifier!r} not found.",
        )


session_repository = SessionRepository()