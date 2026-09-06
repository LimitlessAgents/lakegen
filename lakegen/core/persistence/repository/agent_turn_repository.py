from collections.abc import Mapping

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.core.persistence.repository.base import Repository


class AgentTurnRepository(Repository):
    def create(self, data: Mapping[str, object]) -> None:
        payload = dict(data)
        turn_id = self._required_string(payload, "id")
        session_id = self._required_string(payload, "session_id")
        result = payload.get("result")
        if not isinstance(result, Mapping):
            raise ValueError("result must be an object.")

        try:
            self._database.insert(
                "agent_turns",
                {
                    "id": turn_id,
                    "session_id": session_id,
                    "result": Jsonb(dict(result)),
                },
            )
        except UniqueViolation as error:
            raise BaseError(
                ErrorCode.ALREADY_EXISTS,
                f"Agent turn {turn_id!r} already exists.",
            ) from error

    def get(self, identifier: str) -> dict[str, object]:
        row = self._database.fetch_one(
            """
            SELECT id, session_id, result, created_at
            FROM agent_turns
            WHERE id = %s
            """,
            (identifier,),
        )
        if row is None:
            self._raise_not_found(identifier)
        return row

    def exists(self, identifier: str) -> bool:
        if not identifier:
            return False
        return (
            self._database.fetch_one(
                "SELECT 1 AS found FROM agent_turns WHERE id = %s",
                (identifier,),
            )
            is not None
        )

    def delete(self, identifier: str) -> None:
        row = self._database.fetch_one(
            "DELETE FROM agent_turns WHERE id = %s RETURNING id",
            (identifier,),
        )
        if row is None:
            self._raise_not_found(identifier)

    @staticmethod
    def _raise_not_found(identifier: str) -> None:
        raise BaseError(
            ErrorCode.NOT_FOUND,
            f"Agent turn {identifier!r} not found.",
        )


agent_turn_repository = AgentTurnRepository()
