"""``inspect_files`` tool: list data files in a table snapshot.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
"""

from lakegen.tool.iceberg.model import TimeTravelInspectArguments
from lakegen.tool.registry import registry

_DESCRIPTION = (
    "Returns data files for a table snapshot (file_path, format, record counts, "
    "sizes, column metrics). "
    "Use for file-level inspection or small-file analysis. "
    "Optionally pass snapshot_id to inspect files at a historical snapshot. "
)


def inspect_files(arguments: TimeTravelInspectArguments, catalog):
    return catalog.inspect_files(
        arguments.table,
        snapshot_id=arguments.snapshot_id,
        limit=arguments.limit,
    )


registry.register(
    name="inspect_files",
    description=_DESCRIPTION,
    arguments_model=TimeTravelInspectArguments,
    handler=inspect_files,
    requires_catalog=True,
)
