"""Compaction analysis: determine whether tables need file compaction.

Evaluates small-file ratio and delete-file thresholds on a per-partition
basis (or as a single unit for unpartitioned tables).

Delete file types by format version:
  V2: equality deletes + position deletes
  V3: equality deletes + deletion vectors
"""

from __future__ import annotations

from collections import Counter
from typing import Any
from urllib.parse import quote_plus

from lakegen.tool.iceberg.model import CatalogTableArguments
from lakegen.tool.registry import registry

# Default target file size: 256 MB
_DEFAULT_TARGET_FILE_SIZE_BYTES = 256 * 1024 * 1024

# A data file smaller than this fraction of the target size is "small".
_SMALL_FILE_FRACTION = 0.5

# If more than this fraction of a partition's data files are small, or it has
# more delete files than this, compaction is recommended.
_SMALL_FILE_RATIO_THRESHOLD = 0.5
_DELETE_FILE_COUNT_THRESHOLD = 10

_DESCRIPTION = (
    "Evaluates whether an Iceberg table needs compaction. Analyzes small file ratio "
    "and delete file thresholds per partition (or as a whole table if unpartitioned)."
)


def _get_target_file_size(properties: dict[str, Any]) -> int:
    """Read target file size from table properties, falling back to default."""
    try:
        return int(
            properties.get(
                "write.target-file-size-bytes", _DEFAULT_TARGET_FILE_SIZE_BYTES
            )
        )
    except (TypeError, ValueError):
        return _DEFAULT_TARGET_FILE_SIZE_BYTES


def _partition_key(partition: dict[str, Any] | None) -> str:
    """Return an unambiguous key; separators inside values are escaped."""
    if not partition:
        return "unpartitioned"
    return "/".join(
        f"{quote_plus(str(key), safe='')}={quote_plus(str(value), safe='')}"
        for key, value in sorted(partition.items())
    )


def _analyze_partition(
    files: list[dict[str, Any]],
    target_file_size: int,
) -> dict[str, Any]:
    """Compute compaction metrics for a single partition bucket."""
    small_threshold = target_file_size * _SMALL_FILE_FRACTION
    data_files = [f for f in files if f.get("content") == 0]
    delete_files = Counter(f.get("content") for f in files if f.get("content"))

    total_data_files = len(data_files)
    small_file_count = sum(
        (f.get("file_size_in_bytes") or 0) < small_threshold for f in data_files
    )
    small_file_ratio = (
        small_file_count / total_data_files if total_data_files else 0.0
    )
    total_delete_files = sum(delete_files.values())

    too_many_small_files = (
        total_data_files > 1
        and small_file_ratio > _SMALL_FILE_RATIO_THRESHOLD
    )
    too_many_delete_files = total_delete_files > _DELETE_FILE_COUNT_THRESHOLD

    reasons: list[str] = []
    if too_many_small_files:
        reasons.append(
            f"small file ratio {small_file_ratio:.1%} exceeds "
            f"threshold {_SMALL_FILE_RATIO_THRESHOLD:.0%} "
            f"({small_file_count}/{total_data_files} files "
            f"< {small_threshold / (1024 * 1024):.0f} MB)"
        )
    if too_many_delete_files:
        reasons.append(
            f"delete file count {total_delete_files} exceeds "
            f"threshold {_DELETE_FILE_COUNT_THRESHOLD}"
        )

    return {
        "needs_compaction": too_many_small_files or too_many_delete_files,
        "reasons": reasons,
        "total_data_files": total_data_files,
        "small_file_count": small_file_count,
        "small_file_ratio": round(small_file_ratio, 4),
        "equality_delete_files": delete_files[2],
        "position_delete_files": delete_files[1],
        "deletion_vector_files": delete_files[3],
        "total_delete_files": total_delete_files,
        "target_file_size_bytes": target_file_size,
    }


def is_compaction_needed(
    arguments: CatalogTableArguments,
    catalog,
) -> dict[str, Any]:
    """Return per-partition compaction recommendations for one table."""
    table_name = arguments.table
    metadata = catalog.get_table_metadata(table_name)
    target_file_size = _get_target_file_size(metadata.get("properties") or {})
    format_version = (
        metadata.get("format_version")
        or metadata.get("format-version")
        or 2
    )

    default_spec_id = (
        metadata.get("default_spec_id")
        or metadata.get("default-spec-id")
        or 0
    )
    partition_specs = (
        metadata.get("partition_specs")
        or metadata.get("partition-specs")
        or []
    )
    active_spec = next(
        (spec for spec in partition_specs if spec.get("spec-id") == default_spec_id),
        None,
    )
    is_partitioned = bool(active_spec and active_spec.get("fields"))

    # Group every file (the catalog does not truncate) by partition label.
    partition_buckets: dict[str, list[dict[str, Any]]] = {}
    for row in catalog.inspect_files(table_name):
        key = (
            _partition_key(row.get("partition"))
            if is_partitioned
            else "unpartitioned"
        )
        partition_buckets.setdefault(key, []).append(row)

    if not partition_buckets:
        partition_buckets["unpartitioned"] = []

    partitions = {
        key: _analyze_partition(files, target_file_size)
        for key, files in partition_buckets.items()
    }
    return {
        "table": table_name,
        "format_version": format_version,
        "is_partitioned": is_partitioned,
        "needs_compaction": any(
            analysis["needs_compaction"] for analysis in partitions.values()
        ),
        "partitions": partitions,
    }


registry.register(
    name="is_compaction_needed",
    description=_DESCRIPTION,
    arguments_model=CatalogTableArguments,
    handler=is_compaction_needed,
    requires_catalog=True,
)
