"""``inspect_history`` tool: show when snapshots became current.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
"""

from lakegen.tool.iceberg.model import InspectTableArguments
from lakegen.tool.registry import registry

_DESCRIPTION = (
    "Returns snapshot ancestry history for a table (made_current_at, snapshot_id, "
    "parent_id, is_current_ancestor). "
    "Use to understand which snapshots were current and how they relate. "
)


def inspect_history(arguments: InspectTableArguments, catalog):
    return catalog.inspect_history(arguments.table, limit=arguments.limit)


registry.register(
    name="inspect_history",
    description=_DESCRIPTION,
    arguments_model=InspectTableArguments,
    handler=inspect_history,
    requires_catalog=True,
)
