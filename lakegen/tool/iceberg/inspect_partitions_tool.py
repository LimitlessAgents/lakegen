"""``inspect_partitions`` tool: summarize partition layout for a table.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
"""

from lakegen.tool.iceberg.model import TimeTravelInspectArguments
from lakegen.tool.registry import registry

_DESCRIPTION = (
    "Returns partition summaries for a table (partition values, record and file "
    "counts, data file sizes). "
    "Use to understand how a table is partitioned and how large each partition is. "
    "Optionally pass snapshot_id to inspect partitions at a historical snapshot. "
)


def inspect_partitions(arguments: TimeTravelInspectArguments, catalog):
    return catalog.inspect_partitions(
        arguments.table,
        snapshot_id=arguments.snapshot_id,
        limit=arguments.limit,
    )


registry.register(
    name="inspect_partitions",
    description=_DESCRIPTION,
    arguments_model=TimeTravelInspectArguments,
    handler=inspect_partitions,
    requires_catalog=True,
)
