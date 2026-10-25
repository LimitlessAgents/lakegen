"""Tests for is_compaction_needed's file and partition handling."""

from lakegen.tool.iceberg.is_compaction_needed_tool import is_compaction_needed
from lakegen.tool.iceberg.model import CatalogTableArguments

_MB = 1024 * 1024


def _metadata() -> dict:
    return {
        "format-version": 2,
        "properties": {},
        "default-spec-id": 1,
        "partition-specs": [
            {
                "spec-id": 1,
                "fields": [
                    {
                        "source-id": 1,
                        "field-id": 1000,
                        "transform": "identity",
                        "name": "day",
                    }
                ],
            }
        ],
    }


class FakeCatalog:
    def __init__(self, files):
        self.files = files

    def get_table_metadata(self, table_name):
        return _metadata()

    def inspect_files(self, table_name):
        return self.files


def _data_file(partition: dict, size_bytes: int) -> dict:
    return {
        "content": 0,
        "partition": partition,
        "record_count": 1,
        "file_size_in_bytes": size_bytes,
    }


def test_compaction_reads_files_beyond_first_page():
    files = [
        _data_file({"day": "2024-01-01"}, 200 * _MB) for _ in range(100)
    ] + [_data_file({"day": "2024-01-01"}, 1024) for _ in range(200)]
    catalog = FakeCatalog(files)

    result = is_compaction_needed(
        CatalogTableArguments(name="prod", table="sales.orders"),
        catalog,
    )

    assert result["needs_compaction"] is True
    assert result["partitions"]["day=2024-01-01"]["total_data_files"] == 300


def test_compaction_keeps_colliding_partition_strings_separate():
    files = [
        _data_file({"a": "x/b=y", "b": "z"}, 1024),
        _data_file({"a": "x", "b": "y/b=z"}, 1024),
    ]
    catalog = FakeCatalog(files)

    result = is_compaction_needed(
        CatalogTableArguments(name="prod", table="sales.orders"),
        catalog,
    )

    # Each partition has one small file, so neither crosses the multi-file
    # threshold. A colliding string key would combine them into one bad bucket.
    assert result["needs_compaction"] is False
    assert len(result["partitions"]) == 2


def test_compaction_counts_delete_files():
    partition = {"day": "2024-01-01"}
    files = [_data_file(partition, 200 * _MB)] + [
        {"content": 1, "partition": partition, "file_size_in_bytes": 1024}
        for _ in range(11)
    ]
    catalog = FakeCatalog(files)

    result = is_compaction_needed(
        CatalogTableArguments(name="prod", table="sales.orders"),
        catalog,
    )

    analysis = result["partitions"]["day=2024-01-01"]
    assert analysis["position_delete_files"] == 11
    assert analysis["total_delete_files"] == 11
    assert analysis["needs_compaction"] is True
