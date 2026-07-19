"""``list_namespaces`` tool: list namespaces in a registered catalog.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
"""

from pydantic import BaseModel, ConfigDict, Field

from lakegen.core.connection.registry import conreg
from lakegen.tool.registry import registry

_CONNECTION_KIND = "catalog"
_DESCRIPTION = (
    "Returns namespace names in an Iceberg catalog for a given connection name. "
    "Use to list namespaces in a registered catalog connection. "
)


class ListNamespacesArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Name of the catalog connection.")


def list_namespaces(arguments: ListNamespacesArguments):
    catalog = conreg.get_connection(_CONNECTION_KIND, arguments.name)
    return catalog.list_namespaces()


registry.register(
    toolset=_CONNECTION_KIND,
    name="list_namespaces",
    description=_DESCRIPTION,
    arguments_model=ListNamespacesArguments,
    handler=list_namespaces,
)
