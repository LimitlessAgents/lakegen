from typing import Self

from lakegen.core.catalog.base import BaseCatalog
from lakegen.core.catalog.model import BaseIcebergCatalogSpec
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode


class IcebergCatalog(BaseCatalog):
    """PyIceberg-backed catalog implementation."""

    def __init__(self, spec: BaseIcebergCatalogSpec):
        self.spec = spec
        self.catalog = None

    @property
    def name(self) -> str:
        return self.spec.name

    def connect(self) -> Self:
        from pyiceberg.catalog import load_catalog

        try:
            name, properties = self.spec.pyiceberg_kwargs()
            self.catalog = load_catalog(name, **properties)
            return self
        except Exception as e:
            raise BaseError(ErrorCode.CONNECTION_FAILED, f"Failed to connect to the catalog, {e}")

    def list_namespaces(self):
        try:
            return self.catalog.list_namespaces()
        except Exception as e:
            raise BaseError(ErrorCode.INTERNAL, f"Failed to list namespaces: {e}", cause=e)

    def list_tables(self, namespace: str):
        try:
            return self.catalog.list_tables(namespace=namespace)
        except Exception as e:
            raise BaseError(ErrorCode.INTERNAL, "Failed to list tables", cause=e)

    def load_table(self, table_name: str):
        try:
            return self.catalog.load_table(table_name)
        except Exception as e:
            raise BaseError(ErrorCode.INTERNAL, "Failed to load table", cause=e)

    def close(self) -> None:
        self.catalog.close()
        self.catalog = None
