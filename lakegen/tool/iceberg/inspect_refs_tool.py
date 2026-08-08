"""``inspect_refs`` tool: list branches and tags for a table.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
"""

from lakegen.core.connection.registry import conreg
from lakegen.tool.iceberg.model import InspectTableArguments
from lakegen.tool.registry import registry

_CONNECTION_KIND = "catalog"
_DESCRIPTION = (
    "Returns snapshot references for a table (branches and tags with snapshot_id "
    "and retention settings). "
    "Use to see named refs pointing at snapshots. "
)


def inspect_refs(arguments: InspectTableArguments):
    catalog = conreg.get_connection(_CONNECTION_KIND, arguments.name)
    return catalog.inspect_refs(arguments.table, limit=arguments.limit)


registry.register(
    name="inspect_refs",
    description=_DESCRIPTION,
    arguments_model=InspectTableArguments,
    handler=inspect_refs,
)
