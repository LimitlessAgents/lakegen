from __future__ import annotations

from collections.abc import Mapping

from psycopg import Connection
from psycopg.types.json import Jsonb

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.core.persistence.repository.base import Repository


class AgentTurnRepository(Repository):
    def create(
        self,
        data: Mapping[str, object],
        *,
        connection: Connection | None = None,
    ) -> int:
        payload = dict(data)
        session_id = self._required_string(payload, "session_id")
        result = payload.get("result")
        if not isinstance(result, Mapping):
            raise ValueError("result must be an object.")

        row = self._database.insert(
            "agent_turns",
            {
                "session_id": session_id,
                "result": Jsonb(dict(result)),
            },
            returning="id",
            connection=connection,
        )
        if row is None:
            raise RuntimeError("Agent turn insert did not return an id.")
        return int(row["id"])

    def get(self, identifier: int) -> dict[str, object]:
        row = self._database.fetch_one(
            """
            SELECT *
            FROM agent_turns
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
        limit: int | None = 20,
    ) -> list[dict[str, object]]:
        query = """
            SELECT id, result, created_at
            FROM agent_turns
            WHERE session_id = %s
            ORDER BY id DESC
            OFFSET %s
        """
        params: list[object] = [identifier, offset]
        if limit is not None:
            query += " LIMIT %s"
            params.append(limit)
        return self._database.fetch_all(query, tuple(params))

    def latest_id(self, identifier: str) -> int | None:
        row = self._database.fetch_one(
            "SELECT id FROM agent_turns WHERE session_id = %s ORDER BY id DESC LIMIT 1",
            (identifier,),
        )
        return int(row["id"]) if row is not None else None

    def list_where(
        self,
        identifier: str,
        condition: str,
        params: tuple[object, ...] = (),
        offset: int = 0,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        query = f"""
            SELECT id, result, created_at
            FROM agent_turns
            WHERE session_id = %s AND ({condition})
            ORDER BY id DESC
        """
        all_params: list[object] = [identifier, *params]
        if offset > 0:
            query += " OFFSET %s"
            all_params.append(offset)
        if limit is not None:
            query += " LIMIT %s"
            all_params.append(limit)
        return self._database.fetch_all(query, tuple(all_params))

    def exists(self, identifier: int) -> bool:
        return (
            self._database.fetch_one(
                "SELECT 1 AS found FROM agent_turns WHERE id = %s",
                (identifier,),
            )
            is not None
        )

    def delete(self, identifier: int) -> None:
        row = self._database.fetch_one(
            "DELETE FROM agent_turns WHERE id = %s RETURNING id",
            (identifier,),
        )
        if row is None:
            self._raise_not_found(identifier)

    @staticmethod
    def _raise_not_found(identifier: object) -> None:
        raise BaseError(
            ErrorCode.NOT_FOUND,
            f"Agent turn {identifier!r} not found.",
        )


agent_turn_repository = AgentTurnRepository()
