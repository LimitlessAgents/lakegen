"""Compaction analysis: determine whether tables need file compaction.

Evaluates small-file ratio and delete-file thresholds on a per-partition
basis (or as a single unit for unpartitioned tables).

Delete file types by format version:
  V2: equality deletes + position deletes
  V3: equality deletes + deletion vectors
"""

from __future__ import annotations

from typing import Any

from lakegen.tool.iceberg.model import CatalogTableArguments
from lakegen.tool.registry import registry

# Default target file size: 256 MB
_DEFAULT_TARGET_FILE_SIZE_BYTES = 256 * 1024 * 1024

# A data file smaller than this fraction of the target size is "small".
_SMALL_FILE_FRACTION = 0.5

# If more than this fraction of data files in a partition are small,
# compaction is recommended.
_SMALL_FILE_RATIO_THRESHOLD = 0.5

# If the total number of delete files (any kind) in a partition exceeds
# this count, compaction is recommended.
_DELETE_FILE_COUNT_THRESHOLD = 10


_DESCRIPTION = (
    "Evaluates whether an Iceberg table needs compaction. Analyzes small file ratio "
    "and delete file thresholds per partition (or as a whole table if unpartitioned)."
)

# TODO: is_compaction_needed should also consider the rate of data being
# ingested based on historical snapshot data. High-ingestion partitions may
# benefit from delaying compaction to batch more files, while low-ingestion
# partitions with accumulated small files should be compacted sooner.


def _get_target_file_size(properties: dict[str, Any]) -> int:
    """Read target file size from table properties, falling back to default."""
    raw = properties.get("write.target-file-size-bytes")
    if raw is not None:
        try:
            return int(raw)
        except (ValueError, TypeError):
            pass
    return _DEFAULT_TARGET_FILE_SIZE_BYTES


def _partition_key(partition: dict[str, Any] | None) -> str:
    """Return a stable string key for a partition record dict.

    Unpartitioned tables have an empty partition dict or ``None``, both of
    which map to ``"__unpartitioned__"``.
    """
    if not partition:
        return "__unpartitioned__"
    parts = [f"{k}={v}" for k, v in sorted(partition.items())]
    return "/".join(parts)


def _analyze_partition(
    files: list[dict[str, Any]],
    target_file_size: int,
) -> dict[str, Any]:
    """Compute compaction metrics for a single partition bucket."""
    small_threshold = target_file_size * _SMALL_FILE_FRACTION

    data_files: list[dict[str, Any]] = []
    equality_delete_files = 0
    position_delete_files = 0
    deletion_vector_files = 0  # V3 DVs; position_deletes = 0 in V3

    for f in files:
        content = f.get("content")
        if content == 0:
            # DATA
            data_files.append(f)
        elif content == 1:
            # POSITION_DELETES (V2) — in V3 this counter stays 0 and DVs
            # are tracked via deletion_vector_files instead.
            position_delete_files += 1
        elif content == 2:
            # EQUALITY_DELETES
            equality_delete_files += 1
        # V3 deletion vectors are represented as content type 3 if present;
        # PyIceberg may also label them differently in future versions.
        elif content == 3:
            deletion_vector_files += 1

    total_data_files = len(data_files)
    small_files = [
        f for f in data_files
        if (f.get("file_size_in_bytes") or 0) < small_threshold
    ]
    small_file_count = len(small_files)
    small_file_ratio = (
        small_file_count / total_data_files if total_data_files > 0 else 0.0
    )

    total_delete_files = (
        equality_delete_files + position_delete_files + deletion_vector_files
    )

    needs_compaction = (
        (small_file_ratio > _SMALL_FILE_RATIO_THRESHOLD and total_data_files > 1)
        or total_delete_files > _DELETE_FILE_COUNT_THRESHOLD
    )

    reasons: list[str] = []
    if small_file_ratio > _SMALL_FILE_RATIO_THRESHOLD and total_data_files > 1:
        reasons.append(
            f"small file ratio {small_file_ratio:.1%} exceeds "
            f"threshold {_SMALL_FILE_RATIO_THRESHOLD:.0%} "
            f"({small_file_count}/{total_data_files} files "
            f"< {small_threshold / (1024 * 1024):.0f} MB)"
        )
    if total_delete_files > _DELETE_FILE_COUNT_THRESHOLD:
        reasons.append(
            f"delete file count {total_delete_files} exceeds "
            f"threshold {_DELETE_FILE_COUNT_THRESHOLD}"
        )

    return {
        "needs_compaction": needs_compaction,
        "reasons": reasons,
        "total_data_files": total_data_files,
        "small_file_count": small_file_count,
        "small_file_ratio": round(small_file_ratio, 4),
        "equality_delete_files": equality_delete_files,
        "position_delete_files": position_delete_files,
        "deletion_vector_files": deletion_vector_files,
        "total_delete_files": total_delete_files,
        "target_file_size_bytes": target_file_size,
    }


def _analyze_single_table(table_name: str, catalog) -> dict[str, Any]:
    # ── Table metadata ──────────────────────────────────────────
    metadata = catalog.get_table_metadata(table_name)
    properties = metadata.get("properties") or {}
    target_file_size = _get_target_file_size(properties)
    format_version = (
        metadata.get("format_version")
        or metadata.get("format-version")
        or 2
    )

    # Determine if table is partitioned
    partition_specs = (
        metadata.get("partition_specs")
        or metadata.get("partition-specs")
        or []
    )
    default_spec_id = (
        metadata.get("default_spec_id")
        or metadata.get("default-spec-id")
        or 0
    )
    active_spec = next(
        (s for s in partition_specs if s.get("spec-id") == default_spec_id),
        None,
    )
    is_partitioned = bool(
        active_spec and active_spec.get("fields")
    )

    # ── File-level data ─────────────────────────────────────────
    files_result = catalog.inspect_files(table_name)
    file_rows = (
        files_result.get("rows", [])
        if isinstance(files_result, dict)
        else files_result
    )

    # Bucket files by partition
    partition_buckets: dict[str, list[dict[str, Any]]] = {}
    for row in file_rows:
        if is_partitioned:
            key = _partition_key(row.get("partition"))
        else:
            key = "__unpartitioned__"

        partition_buckets.setdefault(key, []).append(row)

    # ── Per-partition analysis ──────────────────────────────────
    partition_results: dict[str, Any] = {}
    any_needs_compaction = False

    for pkey, pfiles in partition_buckets.items():
        analysis = _analyze_partition(pfiles, target_file_size)
        partition_results[pkey] = analysis
        if analysis["needs_compaction"]:
            any_needs_compaction = True

    # If no files exist at all, nothing to compact
    if not partition_buckets:
        partition_results["__unpartitioned__"] = _analyze_partition(
            [], target_file_size
        )

    return {
        "table": table_name,
        "format_version": format_version,
        "is_partitioned": is_partitioned,
        "needs_compaction": any_needs_compaction,
        "partitions": partition_results,
    }


def is_compaction_needed(
    arguments: CatalogTableArguments | list[CatalogTableArguments],
    catalog,
) -> dict[str, Any]:
    """Analyze tables and return per-partition compaction recommendations.

    Returns a dict containing:
    - ``table``: Table name.
    - ``format_version``: Iceberg format version (2 or 3).
    - ``is_partitioned``: Whether the table has partition fields.
    - ``partitions``: A dict mapping partition keys to analysis results.
    - ``needs_compaction``: ``True`` if *any* partition needs compaction.
    """
    if isinstance(arguments, (list, tuple)):
        results: dict[str, Any] = {}
        for entry in arguments:
            table_name = entry.table if hasattr(entry, "table") else entry["table"]
            results[table_name] = _analyze_single_table(table_name, catalog)
        return results

    table_name = arguments.table if hasattr(arguments, "table") else arguments["table"]
    return _analyze_single_table(table_name, catalog)


registry.register(
    name="is_compaction_needed",
    description=_DESCRIPTION,
    arguments_model=CatalogTableArguments,
    handler=is_compaction_needed,
    requires_catalog=True,
)