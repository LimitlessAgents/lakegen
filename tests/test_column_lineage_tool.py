"""Tests for inspect_column_lineage's metadata-log processing."""

from lakegen.tool.iceberg.column_lineage_tool import inspect_column_lineage
from lakegen.tool.iceberg.model import ColumnLineageArguments


class FakeCatalog:
    def __init__(self, metadata, files=None):
        self.metadata = metadata
        self.files = files or {}

    def get_table_metadata(self, table_name):
        return self.metadata

    def read_metadata_file(self, table_name, metadata_file):
        return self.files[metadata_file]


def test_inspect_column_lineage_detects_added_column():
    old_metadata = {
        "current-schema-id": 0,
        "current-snapshot-id": 7,
        "schemas": [
            {
                "schema-id": 0,
                "fields": [
                    {"id": 1, "name": "id", "type": "long", "required": True}
                ],
            }
        ],
    }
    metadata = {
        "current-schema-id": 1,
        "current-snapshot-id": 7,
        "last-updated-ms": 2_000,
        "metadata-location": "s3://meta/current.json",
        "schemas": [
            {
                "schema-id": 0,
                "fields": [
                    {"id": 1, "name": "id", "type": "long", "required": True}
                ],
            },
            {
                "schema-id": 1,
                "fields": [
                    {"id": 1, "name": "id", "type": "long", "required": True},
                    {
                        "id": 3,
                        "name": "new_col",
                        "type": "string",
                        "required": False,
                    },
                ],
            },
        ],
        "metadata-log": [
            {"timestamp-ms": 1_000, "metadata-file": "s3://meta/old.json"}
        ],
    }
    catalog = FakeCatalog(metadata, {"s3://meta/old.json": old_metadata})

    result = inspect_column_lineage(
        ColumnLineageArguments(
            name="prod",
            table="sales.orders",
            column="new_col",
        ),
        catalog,
    )

    assert result["field_id"] == 3
    assert result["change_detected"] is True
    assert result["changes"][0]["change_type"] == "added"
    assert result["changes"][0]["metadata_timestamp"] == 2_000
    assert result["changes"][0]["snapshot_attribution"] == "metadata_only"
