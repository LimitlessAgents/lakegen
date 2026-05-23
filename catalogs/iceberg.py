from catalogs.base import BaseCatalog
from catalogs.models import CatalogSpec

from pyiceberg.catalog import load_catalog


class IcebergCatalog(BaseCatalog):
    def __init__(self, spec):
        
        self.spec = CatalogSpec.model_validate(spec)

        self.catalog = load_catalog(
            **self.spec.model_dump()
        )

    def list_databases(self):
        if not self.catalog:
            raise "Catalog is not connected"
        return self.catalog.list_namespaces()
    
    def list_tables(self, database: str):
        if not self.catalog:
            raise "Catalog is not connected"
        return self.catalog.list_tables(namespace=database)

    def load_table(self, table_name: str):
        if not self.catalog:
            raise "Catalog is not connected"
        return self.catalog.load_table(table_name)
