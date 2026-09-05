"""``list_tables`` tool: list tables in a namespace of the session catalog.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
"""

from lakegen.tool.iceberg.model import CatalogNamespaceArguments
from lakegen.tool.registry import registry

_DESCRIPTION = (
    "Returns table names in a namespace for the session's active catalog. "
    "Use to list tables in a namespace. "
    "Do not use to list namespaces instead."
)


def list_tables(arguments: CatalogNamespaceArguments, catalog):
    return catalog.list_tables(arguments.namespace)


registry.register(
    name="list_tables",
    description=_DESCRIPTION,
    arguments_model=CatalogNamespaceArguments,
    handler=list_tables,
    requires_catalog=True,
)
