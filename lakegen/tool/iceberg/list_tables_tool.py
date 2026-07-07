"""``list_tables`` tool: list tables in a namespace of a registered catalog.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
"""

from pydantic import BaseModel, ConfigDict, Field

from lakegen.core.connection.registry import conreg
from lakegen.tool.registry import registry

_CONNECTION_KIND = "catalog"
_DESCRIPTION = (
    "Returns table names in a namespace for a given catalog connection. "
    "Use to list tables in a namespace of a registered catalog connection. "
    "Do not use if no connection exists for that name, or to list namespaces instead."
)


class ListTablesParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Name of the catalog connection.")
    namespace: str = Field(description="Namespace to list tables from.")


def list_tables(params: ListTablesParams):
    catalog = conreg.get_connection(_CONNECTION_KIND, params.name)
    return catalog.list_tables(params.namespace)


registry.register(
    toolset=_CONNECTION_KIND,
    name="list_tables",
    description=_DESCRIPTION,
    params_model=ListTablesParams,
    handler=list_tables,
)
