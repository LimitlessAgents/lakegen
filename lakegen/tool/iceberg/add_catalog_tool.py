"""``add_catalog`` tool: register and open a new catalog connection.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
"""

from lakegen.core.catalog.model import CatalogSpecArguments, ResolvedCatalogSpec
from lakegen.core.connection.registry import conreg
from lakegen.tool.registry import registry

_CONNECTION_KIND = "catalog"
_DESCRIPTION = (
    "Registers and opens a new catalog connection and saves credentials for reuse. "
    "Use for an unregistered catalog after choosing glue, rest, or sql and collecting "
    "required details and secrets from the user. "
)


def add_catalog(arguments: ResolvedCatalogSpec) -> None:
    conreg.open_new_connection(_CONNECTION_KIND, arguments)


registry.register(
    toolset=_CONNECTION_KIND,
    name="add_catalog",
    description=_DESCRIPTION,
    arguments_model=CatalogSpecArguments,
    handler=add_catalog,
    requires_env=True,
)
