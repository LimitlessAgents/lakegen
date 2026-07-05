"""``list_namespaces`` tool: list namespaces in a registered catalog.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
"""

from pydantic import BaseModel, ConfigDict, Field

from lakegen.core.connection.registry import conreg
from lakegen.tool.registry import registry

_TOOLSET = "catalog"
_DESCRIPTION = (
    "Returns namespace names in an Iceberg catalog for a given connection name. "
    "Use to list namespaces in a registered catalog connection. "
)


class ListNamespacesParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Name of the catalog connection.")


def list_namespaces(params: ListNamespacesParams):
    catalog = conreg.get_connection(_TOOLSET, params.name)
    return catalog.list_namespaces()


registry.register(
    toolset=_TOOLSET,
    name="list_namespaces",
    description=_DESCRIPTION,
    params_model=ListNamespacesParams,
    handler=list_namespaces,
)
