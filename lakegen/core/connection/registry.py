"""Open, cache, and reuse catalog connections."""

from typing import Any

from lakegen.core.catalog.model import ResolvedCatalogSpec, resolve_catalog_spec
from lakegen.core.connection.type.catalog import get_catalog_instance
from lakegen.core.credential.store import get_credentials, store_credentials
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode


class ConnectionRegistry:
    """Keeps open connections in memory and persists creds on first connect."""

    def __init__(self):
        self._open: dict[str, dict[str, Any]] = {
            "catalog": {},
        }
        self._connection_type = {
            "catalog": get_catalog_instance,
        }

    def get_connection(self, kind: str, connection_name: str):
        """Return a cached connection or open one from stored credentials."""
        if connection_name in self._open[kind]:
            return self._open[kind][connection_name]

        try:
            stored = get_credentials(kind, connection_name)
        except BaseError as e:
            raise BaseError(
                ErrorCode.NOT_FOUND,
                f"Failed to get credentials for {connection_name!r}.",
                details=e.to_dict(),
            ) from e

        # Stored creds are JSON; validate once before opening.
        spec = resolve_catalog_spec(stored)

        try:
            return self.open_new_connection(kind, spec)
        except BaseError as e:
            raise BaseError(
                ErrorCode.CONNECTION_FAILED,
                f"No cached connection for {connection_name!r}. Failed to open a new connection.",
                details=e.to_dict(),
            ) from e
        except Exception as e:
            raise BaseError(
                ErrorCode.CONNECTION_FAILED,
                f"Unable to open connection for {connection_name!r}.",
                cause=e,
            ) from e

    def open_new_connection(self, kind: str, params: ResolvedCatalogSpec):
        """Open a connection from a validated spec and save credentials."""
        # Only serialize here — specs stay as objects everywhere else.
        json_params = params.model_dump()

        name = params.name
        if name in self._open[kind]:
            self._open[kind].pop(name).close()

        connection = self._connection_type[kind](params).connect()
        store_credentials(kind, name, json_params)
        self._open[kind][name] = connection
        return connection


conreg = ConnectionRegistry()
