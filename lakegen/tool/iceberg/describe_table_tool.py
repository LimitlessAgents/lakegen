"""``describe_table`` tool: return name, location, and schema for a table.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
"""

from lakegen.tool.iceberg.model import CatalogTableArguments
from lakegen.tool.registry import registry

_DESCRIPTION = (
    "Returns basic metadata for a table: name, storage location, and schema "
    "(field names and types). "
    "Use after listing tables when you need to understand a table's columns. "
)


def describe_table(arguments: CatalogTableArguments, catalog):
    return catalog.get_table_metadata(arguments.table)


registry.register(
    name="describe_table",
    description=_DESCRIPTION,
    arguments_model=CatalogTableArguments,
    handler=describe_table,
    requires_catalog=True,
)
