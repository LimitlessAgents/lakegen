"""``inspect_metadata_log`` tool: list metadata file history for a table.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
"""

from lakegen.tool.iceberg.model import InspectTableArguments
from lakegen.tool.registry import registry

_DESCRIPTION = (
    "Returns metadata log entries for a table (timestamp, metadata file path, "
    "latest snapshot/schema/sequence numbers). "
    "Use to trace metadata file evolution over time. "
)


def inspect_metadata_log(arguments: InspectTableArguments, catalog):
    return catalog.inspect_metadata_log(arguments.table, limit=arguments.limit)


registry.register(
    name="inspect_metadata_log",
    description=_DESCRIPTION,
    arguments_model=InspectTableArguments,
    handler=inspect_metadata_log,
    requires_catalog=True,
)
