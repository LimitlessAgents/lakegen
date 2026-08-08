"""``inspect_partitions`` tool: summarize partition layout for a table.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
"""

from pydantic import BaseModel, ConfigDict, Field

from lakegen.core.connection.registry import conreg
from lakegen.tool.registry import registry

_CONNECTION_KIND = "catalog"
_DESCRIPTION = (
    "Returns partition summaries for a table (partition values, record and file "
    "counts, data file sizes). "
    "Use to understand how a table is partitioned and how large each partition is. "
)


class InspectPartitionsArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Name of the catalog connection.")
    table: str = Field(
        description="Fully qualified table name (e.g. 'sales.orders').",
    )


def inspect_partitions(arguments: InspectPartitionsArguments):
    catalog = conreg.get_connection(_CONNECTION_KIND, arguments.name)
    return catalog.inspect_partitions(arguments.table)


registry.register(
    name="inspect_partitions",
    description=_DESCRIPTION,
    arguments_model=InspectPartitionsArguments,
    handler=inspect_partitions,
)
