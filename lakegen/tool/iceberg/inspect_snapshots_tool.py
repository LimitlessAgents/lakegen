"""``inspect_snapshots`` tool: list snapshot history for a table.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
"""

from lakegen.core.connection.registry import conreg
from lakegen.tool.iceberg.model import CatalogTableArguments
from lakegen.tool.registry import registry

_CONNECTION_KIND = "catalog"
_DESCRIPTION = (
    "Returns snapshot history for a table (committed_at, snapshot_id, parent_id, "
    "operation, summary). "
    "Use to understand how a table changed over time. "
)


def inspect_snapshots(arguments: CatalogTableArguments):
    catalog = conreg.get_connection(_CONNECTION_KIND, arguments.name)
    return catalog.inspect_snapshots(arguments.table)


registry.register(
    name="inspect_snapshots",
    description=_DESCRIPTION,
    arguments_model=CatalogTableArguments,
    handler=inspect_snapshots,
)
