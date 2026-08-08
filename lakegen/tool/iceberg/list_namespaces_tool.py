"""``list_namespaces`` tool: list namespaces in a registered catalog.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
"""

from lakegen.core.connection.registry import conreg
from lakegen.tool.iceberg.model import CatalogConnectionArguments
from lakegen.tool.registry import registry

_CONNECTION_KIND = "catalog"
_DESCRIPTION = (
    "Returns namespace names in an Iceberg catalog for a given connection name. "
    "Use to list namespaces in a registered catalog connection. "
)


def list_namespaces(arguments: CatalogConnectionArguments):
    catalog = conreg.get_connection(_CONNECTION_KIND, arguments.name)
    return catalog.list_namespaces()


registry.register(
    name="list_namespaces",
    description=_DESCRIPTION,
    arguments_model=CatalogConnectionArguments,
    handler=list_namespaces,
)
