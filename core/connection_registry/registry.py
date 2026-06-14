from abc import ABC
from typing import Any

from connection_registry.type.catalog import get_catalog_instance
from credential.store import get_credentials

from credential.store import store_credentials, get_credentials

class ConnectionRegistry:
    def __init__(self):
        self._open: dict[str, dict[str, Any]] = {
            "catalog": {},
        }
        self._connection_type: dict[str, Any] = {
            "catalog": get_catalog_instance,
        }

    def open_connection(self, kind: str, connection_name: str) -> type[ABC]:
        if connection_name in self._open[kind]:
            return self._open[kind][connection_name]
        connection_creds = get_credentials(kind, connection_name)
        return self.open_new_connection(kind, connection_creds)
    
    def open_new_connection(self, kind: str, params: dict[str, Any]):
        name = params["name"]
        if name in self._open[kind]:
            self._open[kind].pop(name).close()
        connection = self._connection_type[kind](params).connect()
        store_credentials(kind, name, params)
        self._open[kind][name] = connection
        return connection



conreg = ConnectionRegistry()
