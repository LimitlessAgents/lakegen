from typing import Self

from lakegen.core.catalog.base import BaseCatalog
from lakegen.core.catalog.model import ResolvedCatalogSpec
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode


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
            self.catalog = load_catalog(name, **properties)
            return self
        except Exception as e:
            # print("============")
            # print(e)
            # print("============")
            raise BaseError(
                ErrorCode.CONNECTION_FAILED,
                "Failed to connect to the catalog.",
            ) from e

    def list_namespaces(self):
        try:
            return self.catalog.list_namespaces()
        except Exception as e:
            raise BaseError(
                ErrorCode.INTERNAL,
                "Failed to list namespaces.",
            ) from e

    def list_tables(self, namespace: str):
        try:
            return self.catalog.list_tables(namespace=namespace)
        except Exception as e:
            raise BaseError(
                ErrorCode.INTERNAL,
                "Failed to list tables.",
            ) from e

    def load_table(self, table_name: str):
        try:
            return self.catalog.load_table(table_name)
        except Exception as e:
            raise BaseError(
                ErrorCode.INTERNAL,
                "Failed to load table.",
            ) from e

    def close(self) -> None:
        # Best-effort teardown: close() failures are ignored because the goal is
        # simply to drop the handle, which the final assignment guarantees.
        try:
            self.catalog.close()
        except Exception:
            pass
        self.catalog = None
