"""``inspect_manifests`` tool: list manifest files for a table.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
"""

from lakegen.core.connection.registry import conreg
from lakegen.tool.iceberg.model import InspectTableArguments
from lakegen.tool.registry import registry

_CONNECTION_KIND = "catalog"
_DESCRIPTION = (
    "Returns current manifest files for a table (path, length, file counts, "
    "partition summaries). "
    "Use to inspect manifest-level layout and compaction state. "
)


def inspect_manifests(arguments: InspectTableArguments):
    catalog = conreg.get_connection(_CONNECTION_KIND, arguments.name)
    return catalog.inspect_manifests(arguments.table, limit=arguments.limit)


registry.register(
    name="inspect_manifests",
    description=_DESCRIPTION,
    arguments_model=InspectTableArguments,
    handler=inspect_manifests,
)
