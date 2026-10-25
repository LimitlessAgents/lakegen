"""``summarize_partitions`` tool: partition layout, volume, and spec history.

Importing this module registers the tool as a side effect. ``_DESCRIPTION`` is
shown to the agent, so it is written as guidance for when/how to call the tool.
All aggregation and metadata-log interpretation happens here; the catalog only
fetches raw PyIceberg data.
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.tool.iceberg.model import CatalogTableArguments
from lakegen.tool.registry import registry

_DESCRIPTION = (
    "Summarizes a table's partition layout and evolution in one call: the active "
    "spec, retained spec definitions, when the active spec changed, data volume "
    "per spec, and live partitions sorted by data size. Only partitions holding "
    "files at the resolved snapshot are returned; Iceberg tracks no empty "
    "partitions. `record_count` is data-file records before deletes. Use "
    "`snapshot_id` for a historical view, `spec_id` to scope the whole report to "
    "one spec, and `offset`/`limit` to page partition rows. Summaries always "
    "cover every matching partition."
)


class PartitionSummaryArguments(CatalogTableArguments):
    snapshot_id: int | None = Field(
        default=None,
        description="Snapshot to summarize. Defaults to the current snapshot.",
    )
    spec_id: int | None = Field(
        default=None,
        description="Limit the report to partitions written under this spec ID.",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description=(
            "Number of partition rows to skip. Rows are sorted by data size "
            "descending."
        ),
    )
    limit: int = Field(
        default=100,
        ge=1,
        description="Maximum partition rows to return. Summaries cover all rows.",
    )
    include_spec_history: bool = Field(
        default=True,
        description=(
            "Read the metadata log to find when the active partition spec "
            "changed. Set false to skip that history scan."
        ),
    )


def _pick(mapping: dict[str, Any], *keys: str, default=None):
    """Read the first present key, accepting PyIceberg kebab/snake aliases."""
    for key in keys:
        if key in mapping:
            return mapping[key]
    return default


def _timestamp_iso(timestamp_ms: int | None) -> str | None:
    if timestamp_ms is None:
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat()


def _spec_definition(spec: dict[str, Any]) -> dict[str, Any]:
    """Normalize one metadata-dump partition spec."""
    return {
        "spec_id": _pick(spec, "spec-id", "spec_id"),
        "fields": [
            {
                "field_id": _pick(field, "field-id", "field_id"),
                "name": _pick(field, "name"),
                "transform": str(_pick(field, "transform")),
                "source_field_id": _pick(field, "source-id", "source_id"),
            }
            for field in _pick(spec, "fields", default=[]) or []
        ],
    }


def _specs_by_id(metadata: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        spec["spec_id"]: spec
        for spec in (
            _spec_definition(item)
            for item in _pick(
                metadata, "partition-specs", "partition_specs", default=[]
            )
            or []
        )
    }


def _version(
    metadata: dict[str, Any],
    timestamp_ms: int,
    metadata_file: str | None,
) -> dict[str, Any]:
    return {
        "timestamp": timestamp_ms,
        "snapshot_id": _pick(
            metadata, "current-snapshot-id", "current_snapshot_id"
        ),
        "default_spec_id": _pick(metadata, "default-spec-id", "default_spec_id"),
        "specs": _specs_by_id(metadata),
        "metadata_file": metadata_file,
    }


def _metadata_versions(
    table_name: str,
    metadata: dict[str, Any],
    catalog,
) -> tuple[list[dict[str, Any]], bool]:
    """Read the metadata log oldest-first, with the spec active at each commit.

    Log entries are walked newest-first so an unreadable old metadata file only
    truncates the oldest tail. The current metadata is appended because it is
    not part of its own log.
    """
    versions: list[dict[str, Any]] = []
    truncated = False

    log = _pick(metadata, "metadata-log", "metadata_log", default=[]) or []
    for entry in reversed(log):
        metadata_file = _pick(entry, "metadata-file", "metadata_file")
        try:
            previous = catalog.read_metadata_file(table_name, metadata_file)
        except BaseError:
            truncated = True
            break
        versions.append(
            _version(
                previous,
                _pick(entry, "timestamp-ms", "timestamp_ms"),
                metadata_file,
            )
        )

    versions.reverse()
    versions.append(
        _version(
            metadata,
            _pick(metadata, "last-updated-ms", "last_updated_ms"),
            _pick(metadata, "metadata-location", "metadata_location"),
        )
    )
    return versions, truncated


def _field_map(spec: dict[str, Any] | None) -> dict[tuple, dict[str, Any]]:
    """Index a spec's fields by identity, ignoring field order."""
    if spec is None:
        return {}
    return {
        (
            field["field_id"],
            field["source_field_id"],
            field["name"],
            field["transform"],
        ): field
        for field in spec["fields"]
    }


def _spec_changes(versions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return active-spec changes between consecutive metadata versions."""
    changes: list[dict[str, Any]] = []
    for older, newer in zip(versions, versions[1:]):
        old_id = older["default_spec_id"]
        new_id = newer["default_spec_id"]
        old_fields = _field_map(older["specs"].get(old_id))
        new_fields = _field_map(newer["specs"].get(new_id))
        if old_id == new_id and old_fields == new_fields:
            continue

        changes.append(
            {
                "timestamp": _timestamp_iso(newer["timestamp"]),
                "spec_id_from": old_id,
                "spec_id_to": new_id,
                "fields_added": [
                    field for key, field in new_fields.items() if key not in old_fields
                ],
                "fields_removed": [
                    field for key, field in old_fields.items() if key not in new_fields
                ],
                "snapshot_id": newer["snapshot_id"],
                "snapshot_attribution": (
                    "exact"
                    if older["snapshot_id"] != newer["snapshot_id"]
                    else "metadata_only"
                ),
            }
        )

    changes.reverse()
    return changes


def _current_field_names(metadata: dict[str, Any]) -> dict[int, str]:
    """Map current-schema field IDs to dotted names for spec source columns."""
    current_id = _pick(metadata, "current-schema-id", "current_schema_id")
    schemas = _pick(metadata, "schemas", default=[]) or []
    schema = next(
        (
            item
            for item in schemas
            if _pick(item, "schema-id", "schema_id") == current_id
        ),
        None,
    )
    names: dict[int, str] = {}

    def walk(fields: list[dict[str, Any]], prefix: str = "") -> None:
        for field in fields:
            name = f"{prefix}{_pick(field, 'name')}"
            names[_pick(field, "id", "field-id", "field_id")] = name
            field_type = _pick(field, "type")
            if isinstance(field_type, dict) and field_type.get("fields"):
                walk(field_type["fields"], f"{name}.")

    if schema:
        walk(_pick(schema, "fields", default=[]) or [])
    return names


def _serialize_specs(
    metadata: dict[str, Any],
    active_spec_id: int,
) -> list[dict[str, Any]]:
    field_names = _current_field_names(metadata)
    specs: list[dict[str, Any]] = []
    for spec_id, spec in sorted(_specs_by_id(metadata).items()):
        for field in spec["fields"]:
            field["source_column"] = field_names.get(field["source_field_id"])
        spec["is_active"] = spec_id == active_spec_id
        spec["observed"] = []
        specs.append(spec)
    return specs


def _resolve_snapshot(
    metadata: dict[str, Any],
    snapshot_id: int | None,
) -> dict[str, Any] | None:
    resolved_id = (
        _pick(metadata, "current-snapshot-id", "current_snapshot_id")
        if snapshot_id is None
        else snapshot_id
    )
    if resolved_id is None:
        return None

    snapshot = next(
        (
            item
            for item in _pick(metadata, "snapshots", default=[]) or []
            if _pick(item, "snapshot-id", "snapshot_id") == resolved_id
        ),
        None,
    )
    if snapshot is None:
        raise BaseError(ErrorCode.NOT_FOUND, "Snapshot not found.")
    return snapshot


def _partition_key(partition: dict[str, Any] | None) -> str:
    """Return a stable, readable key for partition values."""
    if not partition:
        return "unpartitioned"
    return "/".join(f"{key}={value}" for key, value in sorted(partition.items()))


def _partition_totals(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "partition_count": len(rows),
        "data_file_count": sum(row["file_count"] for row in rows),
        "record_count": sum(row["record_count"] for row in rows),
        "data_size_bytes": sum(row["data_size_bytes"] for row in rows),
        "position_delete_file_count": sum(
            row["position_delete_file_count"] for row in rows
        ),
        "position_delete_record_count": sum(
            row["position_delete_record_count"] for row in rows
        ),
        "equality_delete_file_count": sum(
            row["equality_delete_file_count"] for row in rows
        ),
        "equality_delete_record_count": sum(
            row["equality_delete_record_count"] for row in rows
        ),
        "delete_file_count": sum(row["delete_file_count"] for row in rows),
        "delete_record_count": sum(row["delete_record_count"] for row in rows),
    }


def _observed_fields(
    spec: dict[str, Any],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Summarize observed partition values for each field in a spec."""
    observed: list[dict[str, Any]] = []
    for field in spec["fields"]:
        values = [row["partition"].get(field["name"]) for row in rows]
        non_null = [value for value in values if value is not None]
        try:
            distinct = len(set(non_null))
        except TypeError:
            distinct = len({repr(value) for value in non_null})

        entry = {
            "field_id": field["field_id"],
            "name": field["name"],
            "distinct_value_count": distinct,
            "null_partition_count": len(values) - len(non_null),
        }
        # Min/max is only meaningful when the partition value is the source
        # value; bucket/truncate values are not data ranges.
        if field["transform"] == "identity" and non_null:
            try:
                entry["min"] = min(non_null)
                entry["max"] = max(non_null)
            except TypeError:
                pass
        observed.append(entry)
    return observed


def summarize_partitions(
    arguments: PartitionSummaryArguments,
    catalog,
) -> dict[str, Any]:
    table_name = arguments.table
    metadata = catalog.get_table_metadata(table_name)
    active_spec_id = _pick(metadata, "default-spec-id", "default_spec_id")
    specs = _serialize_specs(metadata, active_spec_id)
    active_spec = next(
        (spec for spec in specs if spec["spec_id"] == active_spec_id),
        None,
    )
    is_partitioned = bool(active_spec and active_spec["fields"])

    changes: list[dict[str, Any]] = []
    history_truncated = False
    active_spec_since = None
    if arguments.include_spec_history:
        versions, history_truncated = _metadata_versions(
            table_name, metadata, catalog
        )
        changes = _spec_changes(versions)
        active_spec_since = next(
            (
                change["timestamp"]
                for change in changes
                if change["spec_id_to"] == active_spec_id
            ),
            None,
        )

    snapshot = _resolve_snapshot(metadata, arguments.snapshot_id)
    snapshot_id = (
        _pick(snapshot, "snapshot-id", "snapshot_id") if snapshot else None
    )
    rows: list[dict[str, Any]] = []
    if snapshot is not None:
        for item in catalog.inspect_partitions(
            table_name,
            snapshot_id=snapshot_id,
        ):
            # Unpartitioned tables have no partition/spec columns.
            partition = item.get("partition") or {}
            spec_id = item.get("spec_id", active_spec_id)
            position_files = item.get("position_delete_file_count") or 0
            equality_files = item.get("equality_delete_file_count") or 0
            rows.append(
                {
                    "spec_id": spec_id,
                    "partition": partition,
                    "partition_key": _partition_key(partition),
                    "record_count": item.get("record_count") or 0,
                    "file_count": item.get("file_count") or 0,
                    "data_size_bytes": item.get("total_data_file_size_in_bytes")
                    or 0,
                    "position_delete_file_count": position_files,
                    "position_delete_record_count": item.get(
                        "position_delete_record_count"
                    )
                    or 0,
                    "equality_delete_file_count": equality_files,
                    "equality_delete_record_count": item.get(
                        "equality_delete_record_count"
                    )
                    or 0,
                    "delete_file_count": position_files + equality_files,
                    "delete_record_count": (
                        item.get("position_delete_record_count") or 0
                    )
                    + (item.get("equality_delete_record_count") or 0),
                    "last_updated_at": item.get("last_updated_at")
                    or _timestamp_iso(_pick(snapshot, "timestamp-ms", "timestamp_ms")),
                    "last_updated_snapshot_id": item.get(
                        "last_updated_snapshot_id"
                    )
                    or snapshot_id,
                }
            )

    if arguments.spec_id is not None:
        rows = [row for row in rows if row["spec_id"] == arguments.spec_id]
    rows.sort(
        key=lambda row: (
            -row["data_size_bytes"],
            row["spec_id"],
            row["partition_key"],
        )
    )

    by_spec: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        by_spec.setdefault(row["spec_id"], []).append(row)

    data_by_spec: list[dict[str, Any]] = []
    for spec in specs:
        current_spec_id = spec["spec_id"]
        if arguments.spec_id is not None and current_spec_id != arguments.spec_id:
            continue
        spec_rows = by_spec.get(current_spec_id, [])
        times = [
            row["last_updated_at"] for row in spec_rows if row["last_updated_at"]
        ]
        data_by_spec.append(
            {
                "spec_id": current_spec_id,
                "is_active_spec": current_spec_id == active_spec_id,
                **_partition_totals(spec_rows),
                "oldest_data_at": min(times) if times else None,
                "newest_data_at": max(times) if times else None,
            }
        )
        spec["observed"] = _observed_fields(spec, spec_rows)

    total = len(rows)
    window = rows[arguments.offset : arguments.offset + arguments.limit]
    truncated = arguments.offset + len(window) < total
    return {
        "table": table_name,
        "snapshot": {
            "snapshot_id": snapshot_id,
            "timestamp": _timestamp_iso(
                _pick(snapshot, "timestamp-ms", "timestamp_ms")
            ),
            "is_current": arguments.snapshot_id is None,
        },
        "partitioning": {
            "is_partitioned": is_partitioned,
            "active_spec_id": active_spec_id,
            "active_spec_since": active_spec_since,
            "specs": specs,
        },
        "spec_history": {
            "inspected": arguments.include_spec_history,
            "changes": changes,
            "truncated": history_truncated,
        },
        "summary": _partition_totals(rows),
        "data_by_spec": data_by_spec,
        "partitions": {
            "rows": window,
            "offset": arguments.offset,
            "limit": arguments.limit,
            "total": total,
            "truncated": truncated,
            "next_offset": (
                arguments.offset + len(window) if truncated else None
            ),
        },
    }


registry.register(
    name="summarize_partitions",
    description=_DESCRIPTION,
    arguments_model=PartitionSummaryArguments,
    handler=summarize_partitions,
    requires_catalog=True,
)
