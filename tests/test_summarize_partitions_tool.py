"""Tests for the summarize_partitions tool's processing logic."""

import pytest

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.tool.iceberg.summarize_partitions_tool import (
    PartitionSummaryArguments,
    summarize_partitions,
)


def _field(field_id: int, name: str, source_id: int = 3) -> dict:
    return {
        "source-id": source_id,
        "field-id": field_id,
        "transform": "identity",
        "name": name,
    }


def _spec(spec_id: int, fields: list[dict]) -> dict:
    return {"spec-id": spec_id, "fields": fields}


def _metadata(
    *,
    default_spec_id: int = 1,
    snapshot_id: int | None = 7,
    specs: list[dict] | None = None,
    metadata_log: list[dict] | None = None,
) -> dict:
    snapshots = (
        [{"snapshot-id": snapshot_id, "timestamp-ms": 1_700_000_000_000}]
        if snapshot_id is not None
        else []
    )
    return {
        "current-snapshot-id": snapshot_id,
        "current-schema-id": 0,
        "default-spec-id": default_spec_id,
        "metadata-location": "s3://meta/current.json",
        "last-updated-ms": 1_700_000_000_000,
        "schemas": [
            {
                "schema-id": 0,
                "fields": [
                    {"id": 3, "name": "ts", "type": "timestamp", "required": False}
                ],
            }
        ],
        "partition-specs": specs
        if specs is not None
        else [_spec(1, [_field(1000, "day")])],
        "snapshots": snapshots,
        "metadata-log": metadata_log or [],
    }


def _row(
    day: str,
    size: int,
    *,
    spec_id: int = 1,
    updated_at: str = "2024-01-02T00:00:00+00:00",
) -> dict:
    return {
        "partition": {"day": day},
        "spec_id": spec_id,
        "record_count": 10,
        "file_count": 2,
        "total_data_file_size_in_bytes": size,
        "last_updated_at": updated_at,
        "last_updated_snapshot_id": 7,
    }


class FakeCatalog:
    def __init__(self, metadata, rows=None, files=None):
        self.metadata = metadata
        self.rows = rows or []
        self.files = files or {}
        self.inspected_snapshots = []
        self.read_files = []

    def get_table_metadata(self, table_name):
        return self.metadata

    def inspect_partitions(self, table_name, *, snapshot_id=None):
        self.inspected_snapshots.append(snapshot_id)
        return self.rows

    def read_metadata_file(self, table_name, metadata_file):
        self.read_files.append(metadata_file)
        return self.files[metadata_file]


def _arguments(**overrides) -> PartitionSummaryArguments:
    values = {"name": "prod", "table": "sales.orders"}
    values.update(overrides)
    return PartitionSummaryArguments(**values)


def test_summarize_partitions_aggregates_rows_and_specs():
    catalog = FakeCatalog(
        _metadata(),
        [
            _row("2024-01-01", 1024, updated_at="2024-01-01T00:00:00+00:00"),
            _row("2024-01-02", 2048),
        ],
    )

    result = summarize_partitions(
        _arguments(include_spec_history=False),
        catalog,
    )

    assert result["snapshot"]["snapshot_id"] == 7
    assert result["partitioning"]["is_partitioned"] is True
    assert result["partitioning"]["active_spec_id"] == 1
    assert result["partitioning"]["specs"][0]["fields"][0]["source_column"] == "ts"
    assert result["partitioning"]["specs"][0]["observed"] == [
        {
            "field_id": 1000,
            "name": "day",
            "distinct_value_count": 2,
            "null_partition_count": 0,
            "min": "2024-01-01",
            "max": "2024-01-02",
        }
    ]
    assert result["summary"]["partition_count"] == 2
    assert result["summary"]["data_size_bytes"] == 3072
    assert result["data_by_spec"][0]["data_size_bytes"] == 3072
    assert result["data_by_spec"][0]["oldest_data_at"] == (
        "2024-01-01T00:00:00+00:00"
    )
    assert [row["partition_key"] for row in result["partitions"]["rows"]] == [
        "day=2024-01-02",
        "day=2024-01-01",
    ]
    assert result["spec_history"] == {
        "inspected": False,
        "changes": [],
        "truncated": False,
    }


def test_summarize_partitions_filters_spec_and_pages_rows():
    catalog = FakeCatalog(
        _metadata(),
        [
            _row("2024-01-01", 1024),
            _row("2024-01-02", 2048),
            _row("2024-01-03", 4096),
        ],
    )

    result = summarize_partitions(
        _arguments(include_spec_history=False, offset=1, limit=1),
        catalog,
    )

    assert result["summary"]["partition_count"] == 3
    assert result["partitions"]["total"] == 3
    assert result["partitions"]["truncated"] is True
    assert result["partitions"]["next_offset"] == 2
    assert len(result["partitions"]["rows"]) == 1


def test_summarize_partitions_scopes_report_to_spec():
    catalog = FakeCatalog(_metadata(), [_row("2024-01-01", 1024)])

    result = summarize_partitions(
        _arguments(include_spec_history=False, spec_id=2),
        catalog,
    )

    assert result["summary"]["partition_count"] == 0
    assert result["partitions"]["rows"] == []
    assert result["data_by_spec"] == []


def test_summarize_partitions_includes_spec_history():
    old_metadata = _metadata(
        default_spec_id=0,
        specs=[_spec(0, [])],
        metadata_log=[],
    )
    metadata = _metadata(
        specs=[_spec(0, []), _spec(1, [_field(1000, "day")])],
        metadata_log=[
            {"timestamp-ms": 1_000, "metadata-file": "s3://meta/old.json"}
        ],
    )
    metadata["last-updated-ms"] = 2_000
    catalog = FakeCatalog(
        metadata,
        [_row("2024-01-01", 1024)],
        {"s3://meta/old.json": old_metadata},
    )

    result = summarize_partitions(_arguments(), catalog)

    assert catalog.read_files == ["s3://meta/old.json"]
    assert result["spec_history"]["changes"][0]["spec_id_from"] == 0
    assert result["spec_history"]["changes"][0]["spec_id_to"] == 1
    assert result["spec_history"]["changes"][0]["snapshot_attribution"] == (
        "metadata_only"
    )
    assert result["partitioning"]["active_spec_since"] == (
        "1970-01-01T00:00:02+00:00"
    )


def test_summarize_partitions_passes_historical_snapshot():
    metadata = _metadata(snapshot_id=7)
    metadata["snapshots"].append(
        {"snapshot-id": 123, "timestamp-ms": 1_700_000_001_000}
    )
    catalog = FakeCatalog(metadata)

    result = summarize_partitions(
        _arguments(include_spec_history=False, snapshot_id=123),
        catalog,
    )

    assert catalog.inspected_snapshots == [123]
    assert result["snapshot"]["snapshot_id"] == 123
    assert result["snapshot"]["is_current"] is False


def test_summarize_partitions_missing_snapshot_is_not_found():
    catalog = FakeCatalog(_metadata())

    with pytest.raises(BaseError) as exc_info:
        summarize_partitions(
            _arguments(include_spec_history=False, snapshot_id=999),
            catalog,
        )

    assert exc_info.value.code == ErrorCode.NOT_FOUND


def test_summarize_partitions_handles_unpartitioned_tables():
    catalog = FakeCatalog(
        _metadata(default_spec_id=0, specs=[_spec(0, [])]),
        [
            {
                "record_count": 10,
                "file_count": 2,
                "total_data_file_size_in_bytes": 1024,
            }
        ],
    )

    result = summarize_partitions(
        _arguments(include_spec_history=False),
        catalog,
    )

    assert result["partitioning"]["is_partitioned"] is False
    assert result["partitions"]["rows"][0]["partition_key"] == "__unpartitioned__"
    assert result["data_by_spec"][0]["partition_count"] == 1
