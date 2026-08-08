"""``list_catalogs`` tool: list saved catalog connections.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
"""

from pydantic import BaseModel, ConfigDict

from lakegen.core.connection.registry import conreg
from lakegen.core.credential.store import get_connection_metadata, list_connections
from lakegen.tool.registry import registry

_CONNECTION_KIND = "catalog"
_DESCRIPTION = (
    "Returns registered catalog connections with non-secret metadata and whether "
    "each connection is currently open. "
    "Use to discover which catalogs are available before listing namespaces or tables. "
)

_PUBLIC_FIELDS = ("lakehouse", "catalog_type", "warehouse")


class ListCatalogsArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


def list_catalogs(arguments: ListCatalogsArguments):
    open_names = set(conreg.list_open(_CONNECTION_KIND))
    result = []
    for name in list_connections(_CONNECTION_KIND):
        meta = get_connection_metadata(_CONNECTION_KIND, name)
        entry = {
            "name": name,
            "connected": name in open_names,
        }
        for field in _PUBLIC_FIELDS:
            if field in meta:
                entry[field] = meta[field]
        result.append(entry)
    return result


registry.register(
    name="list_catalogs",
    description=_DESCRIPTION,
    arguments_model=ListCatalogsArguments,
    handler=list_catalogs,
)
