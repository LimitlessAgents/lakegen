"""``describe_table`` tool: return name, location, and schema for a table.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
"""

from pydantic import BaseModel, ConfigDict, Field

from lakegen.core.connection.registry import conreg
from lakegen.tool.registry import registry

_CONNECTION_KIND = "catalog"
_DESCRIPTION = (
    "Returns basic metadata for a table: name, storage location, and schema "
    "(field names and types). "
    "Use after listing tables when you need to understand a table's columns. "
)


class DescribeTableArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Name of the catalog connection.")
    table: str = Field(
        description="Fully qualified table name (e.g. 'sales.orders').",
    )


def describe_table(arguments: DescribeTableArguments):
    catalog = conreg.get_connection(_CONNECTION_KIND, arguments.name)
    return catalog.get_table_metadata(arguments.table)


registry.register(
    name="describe_table",
    description=_DESCRIPTION,
    arguments_model=DescribeTableArguments,
    handler=describe_table,
)
