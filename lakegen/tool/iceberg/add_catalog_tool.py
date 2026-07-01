from lakegen.core.catalog.model import CatalogConnectionSpec, ResolvedCatalogSpec
from lakegen.core.connection.registry import conreg
from lakegen.tool.registry import registry

_TOOLSET = "catalog"
_DESCRIPTION = (
    "Registers and opens a new catalog connection and saves credentials for reuse. "
    "Use for an unregistered catalog after choosing glue, rest, or sql and collecting "
    "required details and secrets from the user. "
)


def add_catalog(params: ResolvedCatalogSpec) -> None:
    conreg.open_new_connection(_TOOLSET, params)


registry.register(
    toolset=_TOOLSET,
    name="add_catalog",
    description=_DESCRIPTION,
    params_model=CatalogConnectionSpec,
    handler=add_catalog,
    requires_env=True,
)
