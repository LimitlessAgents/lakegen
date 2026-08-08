"""``inspect_snapshots`` tool: list snapshot history for a table.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
"""

from pydantic import BaseModel, ConfigDict, Field

from lakegen.core.connection.registry import conreg
from lakegen.tool.registry import registry

_CONNECTION_KIND = "catalog"
_DESCRIPTION = (
    "Returns snapshot history for a table (committed_at, snapshot_id, parent_id, "
    "operation, summary). "
    "Use to understand how a table changed over time. "
)


class InspectSnapshotsArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Name of the catalog connection.")
    table: str = Field(
        description="Fully qualified table name (e.g. 'sales.orders').",
    )


def inspect_snapshots(arguments: InspectSnapshotsArguments):
    catalog = conreg.get_connection(_CONNECTION_KIND, arguments.name)
    return catalog.inspect_snapshots(arguments.table)


registry.register(
    name="inspect_snapshots",
    description=_DESCRIPTION,
    arguments_model=InspectSnapshotsArguments,
    handler=inspect_snapshots,
)
