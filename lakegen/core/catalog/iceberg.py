import logging
from typing import Any, Self

from lakegen.core.catalog.base import BaseCatalog
from lakegen.core.catalog.model import ResolvedCatalogSpec
from lakegen.core.catalog.serialize import arrow_table_to_rows
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode

logger = logging.getLogger(__name__)


class IcebergCatalog(BaseCatalog):
    """Iceberg catalog backed by PyIceberg."""

    def __init__(self, spec: ResolvedCatalogSpec):
        self.spec = spec
        self.catalog = None

    @property
    def name(self) -> str:
        return self.spec.name

    def connect(self) -> Self:
        # Imported lazily so importing this module doesn't pull in PyIceberg
        # (and its heavy transitive deps) until a connection is actually opened.
        from pyiceberg.catalog import load_catalog

        try:
            name, properties = self.spec.iceberg_kwargs()
            logger.debug("Connecting to catalog %r (type=%s)", name, self.spec.catalog_type)
            self.catalog = load_catalog(name, **properties)
            logger.debug("Connected to catalog %r", name)
            return self
        except Exception as e:
            raise BaseError(
                ErrorCode.CONNECTION_FAILED,
                "Failed to connect to the catalog.",
            ) from e

    def list_namespaces(self) -> list[str]:
        """Return namespace names as dotted strings (e.g. ``"sales.q1"``)."""
        try:
            return [".".join(ns) for ns in self.catalog.list_namespaces()]
        except Exception as e:
            raise BaseError(
                ErrorCode.INTERNAL,
                "Failed to list namespaces.",
            ) from e

    def list_tables(self, namespace: str) -> list[str]:
        """Return table names in a namespace as dotted strings."""
        try:
            return [
                ".".join(t) for t in self.catalog.list_tables(namespace=namespace)
            ]
        except Exception as e:
            raise BaseError(
                ErrorCode.INTERNAL,
                "Failed to list tables.",
            ) from e

    def get_table_metadata(self, table_name: str) -> dict[str, Any]:
        """Return table metadata as a plain dict safe for JSON serialization."""
        try:
            table = self.catalog.load_table(table_name)
            return {
                "name": str(table.name()),
                "location": table.location(),
                "schema": {
                    field.name: str(field.field_type)
                    for field in table.schema().fields
                },
            }
        except Exception as e:
            raise BaseError(
                ErrorCode.INTERNAL,
                "Failed to fetch table metadata.",
            ) from e

    def inspect_snapshots(self, table_name: str) -> list[dict[str, Any]]:
        """Return snapshot history as JSON-native rows."""
        try:
            table = self.catalog.load_table(table_name)
            return arrow_table_to_rows(table.inspect.snapshots())
        except Exception as e:
            raise BaseError(
                ErrorCode.INTERNAL,
                "Failed to inspect snapshots.",
            ) from e

    def inspect_partitions(self, table_name: str) -> list[dict[str, Any]]:
        """Return partition summaries as JSON-native rows."""
        try:
            table = self.catalog.load_table(table_name)
            return arrow_table_to_rows(table.inspect.partitions())
        except Exception as e:
            raise BaseError(
                ErrorCode.INTERNAL,
                "Failed to inspect partitions.",
            ) from e

    def close(self) -> None:
        # Best-effort teardown: close() failures are ignored because the goal is
        # simply to drop the handle, which the final assignment guarantees.
        try:
            self.catalog.close()
        except Exception:
            pass
        self.catalog = None
