"""``list_namespaces`` tool: list namespaces in the session catalog.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
"""

from lakegen.tool.iceberg.model import CatalogConnectionArguments
from lakegen.tool.registry import registry

_DESCRIPTION = (
    "Returns namespace names in the session's active Iceberg catalog. "
    "Use to discover namespaces before listing tables. "
)


def list_namespaces(arguments: CatalogConnectionArguments, catalog):
    return catalog.list_namespaces()


registry.register(
    name="list_namespaces",
    description=_DESCRIPTION,
    arguments_model=CatalogConnectionArguments,
    handler=list_namespaces,
    requires_catalog=True,
)
