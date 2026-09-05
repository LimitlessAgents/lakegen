from collections.abc import Mapping

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.core.persistence import PostgresPersistence, persistence


_IDENTITY_FIELDS = frozenset({"name", "lakehouse", "catalog_type"})
_SENSITIVE_FIELDS = frozenset(
    {
        "access_key",
        "credential",
        "glue_access_key",
        "glue_secret_key",
        "password",
        "secret_key",
        "token",
    }
)
_STORED_COLUMNS = "name, lakehouse, catalog_type, config, credentials"
_METADATA_COLUMNS = "name, lakehouse, catalog_type, config"


class CatalogRepository:
    def __init__(
        self,
        database: PostgresPersistence = persistence,
    ) -> None:
        self._database = database

    def create(self, spec: Mapping[str, object]) -> None:
        """Persist public config and credentials in one row."""
        payload = dict(spec)
        name = self._required_string(payload, "name")
        config = {
            key: value
            for key, value in payload.items()
            if key not in _IDENTITY_FIELDS and key not in _SENSITIVE_FIELDS
        }
        credentials = {
            key: value
            for key, value in payload.items()
            if key in _SENSITIVE_FIELDS
        }
        row = {
            "name": name,
            "lakehouse": self._required_string(payload, "lakehouse"),
            "catalog_type": self._required_string(payload, "catalog_type"),
            "config": Jsonb(config),
            "credentials": Jsonb(credentials),
        }

        try:
            self._database.insert("catalogs", row)
        except UniqueViolation as error:
            raise BaseError(
                ErrorCode.ALREADY_EXISTS,
                f"Catalog {name!r} is already registered.",
            ) from error

    def get(self, name: str) -> dict[str, object]:
        """Merge stored config and credentials into a full spec."""
        row = self._database.fetch_one(
            f"SELECT {_STORED_COLUMNS} FROM catalogs WHERE name = %s",
            (name,),
        )
        if row is None:
            self._raise_not_found(name)

        config = row["config"]
        credentials = row["credentials"]
        if not isinstance(config, Mapping):
            raise RuntimeError("Stored catalog config must be an object.")
        if not isinstance(credentials, Mapping):
            raise RuntimeError("Stored catalog credentials must be an object.")
        return {
            **config,
            "name": row["name"],
            "lakehouse": row["lakehouse"],
            "catalog_type": row["catalog_type"],
            **credentials,
        }

    def get_metadata(self, name: str) -> dict[str, object]:
        """Return public metadata without loading credentials."""
        row = self._database.fetch_one(
            f"SELECT {_METADATA_COLUMNS} FROM catalogs WHERE name = %s",
            (name,),
        )
        if row is None:
            self._raise_not_found(name)
        return self._public_metadata(row)

    def list_metadata(self) -> list[dict[str, object]]:
        """Return public metadata for every catalog."""
        rows = self._database.fetch_all(
            f"SELECT {_METADATA_COLUMNS} FROM catalogs ORDER BY name"
        )
        return [self._public_metadata(row) for row in rows]

    def exists(self, name: str) -> bool:
        if not name:
            return False
        return (
            self._database.fetch_one(
                "SELECT 1 AS found FROM catalogs WHERE name = %s",
                (name,),
            )
            is not None
        )

    def delete(self, name: str) -> None:
        row = self._database.fetch_one(
            "DELETE FROM catalogs WHERE name = %s RETURNING name",
            (name,),
        )
        if row is None:
            self._raise_not_found(name)

    @staticmethod
    def _required_string(payload: Mapping[str, object], field: str) -> str:
        value = payload.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field} must be a non-empty string.")
        return value

    @staticmethod
    def _public_metadata(row: Mapping[str, object]) -> dict[str, object]:
        config = row["config"]
        if not isinstance(config, Mapping):
            raise RuntimeError("Stored catalog config must be an object.")
        return {
            "name": row["name"],
            "lakehouse": row["lakehouse"],
            "catalog_type": row["catalog_type"],
            "warehouse": config.get("warehouse"),
        }

    @staticmethod
    def _raise_not_found(name: str) -> None:
        raise BaseError(
            ErrorCode.NOT_FOUND,
            f"Catalog {name!r} is not registered.",
        )


catalog_repository = CatalogRepository()