"""``inspect_entries`` tool: list manifest entries for a table snapshot.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
"""

from lakegen.tool.iceberg.model import TimeTravelInspectArguments
from lakegen.tool.registry import registry

_DESCRIPTION = (
    "Returns manifest entries for a table snapshot, including data and delete "
    "files with readable column metrics. "
    "Use for deeper debugging of table contents at the manifest level. "
    "Optionally pass snapshot_id to inspect entries at a historical snapshot. "
)


def inspect_entries(arguments: TimeTravelInspectArguments, catalog):
    return catalog.inspect_entries(
        arguments.table,
        snapshot_id=arguments.snapshot_id,
        limit=arguments.limit,
    )


registry.register(
    name="inspect_entries",
    description=_DESCRIPTION,
    arguments_model=TimeTravelInspectArguments,
    handler=inspect_entries,
    requires_catalog=True,
)
