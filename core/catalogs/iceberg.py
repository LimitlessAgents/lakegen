from core import BaseError, ErrorCode
from catalogs import BaseCatalog, CatalogSpec

# PyIceberg imports
from pyiceberg.catalog import load_catalog

class IcebergCatalog(BaseCatalog):
    """PyIceberg-backed catalog implementation."""

    def __init__(self, spec):
        
        self.catalog = load_catalog(
            self.spec
        )

    def list_namespaces(self):
        try:
            return self.catalog.list_namespaces()
        except Exception as e:
            raise BaseError(ErrorCode.INTERNAL, "Failed to list namespaces", cause=e)
    
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
