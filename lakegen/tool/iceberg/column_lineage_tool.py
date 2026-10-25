"""``inspect_column_lineage`` tool: trace a column across schema versions.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.

Columns are tracked by their stable field-id, so a rename (same field-id, new
name) is distinguishable from a drop+add (different field-ids). Schema changes
are read from the metadata log because DDL is a metadata-only commit and does
not create a snapshot.
"""

from typing import Any

from lakegen.tool.iceberg.model import ColumnLineageArguments
from lakegen.tool.registry import registry

_DESCRIPTION = (
    "Traces a column across schema versions and reports when it was added, "
    "dropped, renamed, or had its type changed (promoted). Tracks by stable "
    "field-id, so a rename (same field-id, new name) is distinguished from a "
    "drop+add (different field-ids). Results are timestamped by metadata commit; "
    "`snapshot_id` is the snapshot current at that time, and `snapshot_attribution` "
    "is 'metadata_only' when the change did not create a new snapshot. Returns "
    "the first change found in the window; pass `next_offset` to continue older "
    "history. offset/limit count schema-change transitions, newest first."
)


def _pick(mapping: dict[str, Any], *keys: str, default=None):
    """Read the first present key, accepting PyIceberg kebab/snake aliases."""
    for key in keys:
        if key in mapping:
            return mapping[key]
    return default


def _flatten_schema(schema: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Flatten a metadata-dump schema into ``field_id -> state``.

    Field-ids are stable across renames, so keying by them lets callers tell a
    rename (same id, new name) from a drop+add (different ids).
    """
    flat: dict[int, dict[str, Any]] = {}

    def walk(fields: list[dict[str, Any]], prefix: str = "") -> None:
        for field in fields:
            name = f"{prefix}{_pick(field, 'name')}"
            field_type = _pick(field, "type")
            flat[_pick(field, "id", "field-id", "field_id")] = {
                "name": name,
                "type": field_type if isinstance(field_type, str) else str(field_type),
                "required": _pick(field, "required", default=False),
            }
            if isinstance(field_type, dict) and field_type.get("type") == "struct":
                walk(field_type.get("fields", []), f"{name}.")

    walk(_pick(schema, "fields", default=[]) or [])
    return flat


def _schema_history(table_name: str, catalog) -> dict[str, Any]:
    """Read schema versions and the metadata log oldest-first.

    The current metadata retains every schema version. The metadata log is
    walked newest-first so an unreadable old file only truncates the oldest tail.
    """
    metadata = catalog.get_table_metadata(table_name)
    schemas = {
        _pick(schema, "schema-id", "schema_id"): _flatten_schema(schema)
        for schema in _pick(metadata, "schemas", default=[]) or []
    }

    versions: list[dict[str, Any]] = []
    truncated = False
    log = _pick(metadata, "metadata-log", "metadata_log", default=[]) or []
    for entry in reversed(log):
        metadata_file = _pick(entry, "metadata-file", "metadata_file")
        try:
            previous = catalog.read_metadata_file(table_name, metadata_file)
        except Exception:
            truncated = True
            break
        versions.append(
            {
                "timestamp": _pick(entry, "timestamp-ms", "timestamp_ms"),
                "schema_id": _pick(
                    previous, "current-schema-id", "current_schema_id"
                ),
                "snapshot_id": _pick(
                    previous, "current-snapshot-id", "current_snapshot_id"
                ),
                "metadata_file": metadata_file,
            }
        )
    versions.reverse()

    # The current metadata is not part of its own metadata-log.
    versions.append(
        {
            "timestamp": _pick(metadata, "last-updated-ms", "last_updated_ms"),
            "schema_id": _pick(metadata, "current-schema-id", "current_schema_id"),
            "snapshot_id": _pick(
                metadata, "current-snapshot-id", "current_snapshot_id"
            ),
            "metadata_file": _pick(
                metadata, "metadata-location", "metadata_location"
            ),
        }
    )
    return {"schemas": schemas, "versions": versions, "truncated": truncated}


def _parse_decimal(type_name: str) -> tuple[int, int] | None:
    """Parse ``decimal(precision, scale)``; return None for other types."""
    if not type_name.startswith("decimal("):
        return None
    precision, scale = (
        part.strip()
        for part in type_name[len("decimal(") : -1].split(",")
    )
    return int(precision), int(scale)


def _is_type_promotion(old: str, new: str) -> bool:
    """Return True for Iceberg's allowed primitive type promotions."""
    if (old, new) in {("int", "long"), ("float", "double")}:
        return True
    old_decimal = _parse_decimal(old)
    new_decimal = _parse_decimal(new)
    return (
        old_decimal is not None
        and new_decimal is not None
        and new_decimal[1] == old_decimal[1]
        and new_decimal[0] >= old_decimal[0]
    )


def _resolve_field_id(
    schemas: dict[int, dict[int, dict[str, Any]]],
    versions: list[dict[str, Any]],
    column: str,
) -> int | None:
    """Find ``column``'s field-id, preferring the newest schema that has it."""
    for version in reversed(versions):
        for field_id, state in schemas.get(version["schema_id"], {}).items():
            if state["name"] == column:
                return field_id
    return None


def _diff_field(
    field_id: int,
    older_fields: dict[int, dict[str, Any]],
    newer_fields: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return every change to ``field_id`` between two schema versions."""
    old = older_fields.get(field_id)
    new = newer_fields.get(field_id)

    if old is None and new is None:
        return []
    if old is None:
        return [{"change_type": "added", "from_state": None, "to_state": new}]
    if new is None:
        return [{"change_type": "dropped", "from_state": old, "to_state": None}]

    changes: list[dict[str, Any]] = []
    if old["name"] != new["name"]:
        changes.append({"change_type": "renamed", "from_state": old, "to_state": new})
    if old["type"] != new["type"]:
        changes.append(
            {
                "change_type": (
                    "type_promoted"
                    if _is_type_promotion(old["type"], new["type"])
                    else "type_changed"
                ),
                "from_state": old,
                "to_state": new,
            }
        )
    if old["required"] != new["required"]:
        changes.append(
            {"change_type": "nullability_changed", "from_state": old, "to_state": new}
        )
    return changes


def inspect_column_lineage(
    arguments: ColumnLineageArguments,
    catalog,
) -> dict[str, Any]:
    history = _schema_history(arguments.table, catalog)
    schemas = history["schemas"]
    versions = history["versions"]

    # Transitions between consecutive metadata versions whose schema changed.
    transitions = [
        (versions[i - 1], versions[i])
        for i in range(1, len(versions))
        if versions[i]["schema_id"] != versions[i - 1]["schema_id"]
    ]
    transitions.reverse()  # newest first

    window = transitions[arguments.offset : arguments.offset + arguments.limit]
    field_id = _resolve_field_id(schemas, versions, arguments.column)

    result: dict[str, Any] = {
        "table": arguments.table,
        "column": arguments.column,
        "field_id": field_id,
        "change_detected": False,
        "changes": [],
        "window": {
            "offset": arguments.offset,
            "limit": arguments.limit,
            "transitions_examined": len(window),
            "transitions_total": len(transitions),
            "history_truncated": history.get("truncated", False),
        },
    }

    if field_id is None:
        result.update(
            next_offset=None,
            has_more=False,
            exhausted=True,
            origin_reached=False,
            next_step=(
                "Column not found in any retained schema version; it may predate "
                "the available metadata history."
            ),
        )
        return result

    for index, (older, newer) in enumerate(window):
        changes = _diff_field(
            field_id,
            schemas.get(older["schema_id"], {}),
            schemas.get(newer["schema_id"], {}),
        )
        if not changes:
            continue

        consumed = arguments.offset + index + 1
        has_more = consumed < len(transitions)
        snapshot_attribution = (
            "exact" if older["snapshot_id"] != newer["snapshot_id"] else "metadata_only"
        )
        result.update(
            change_detected=True,
            changes=[
                {
                    **change,
                    "metadata_timestamp": newer["timestamp"],
                    "schema_id_from": older["schema_id"],
                    "schema_id_to": newer["schema_id"],
                    "snapshot_id": newer["snapshot_id"],
                    "snapshot_attribution": snapshot_attribution,
                }
                for change in changes
            ],
            next_offset=consumed if has_more else None,
            has_more=has_more,
            exhausted=not has_more,
            origin_reached=(
                any(change["change_type"] == "added" for change in changes)
                or not has_more
            ),
            next_step=(
                f"Call again with offset={consumed} to continue older history."
                if has_more
                else "Reached the oldest retained metadata version."
            ),
        )
        return result

    # No change in this window.
    consumed = arguments.offset + len(window)
    has_more = consumed < len(transitions)
    result.update(
        next_offset=consumed if has_more else None,
        has_more=has_more,
        exhausted=not has_more,
        origin_reached=not has_more,
        next_step=(
            f"Call again with offset={consumed} to continue older history."
            if has_more
            else "Reached the oldest retained metadata version; no change found."
        ),
    )
    return result


registry.register(
    name="inspect_column_lineage",
    description=_DESCRIPTION,
    arguments_model=ColumnLineageArguments,
    handler=inspect_column_lineage,
    requires_catalog=True,
)
