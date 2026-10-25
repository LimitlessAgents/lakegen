"""Tests for inspect_column_lineage's metadata-log processing."""

from lakegen.tool.iceberg.column_lineage_tool import (
    _flatten_schema,
    inspect_column_lineage,
)
from lakegen.tool.iceberg.model import ColumnLineageArguments


class FakeCatalog:
    def __init__(self, metadata, files=None):
        self.metadata = metadata
        self.files = files or {}

    def get_table_metadata(self, table_name):
        return self.metadata

    def read_metadata_file(self, table_name, metadata_file):
        return self.files[metadata_file]


def test_flatten_schema_walks_list_elements_and_map_keys_values():
    schema = {
        "fields": [
            {
                "id": 1,
                "name": "items",
                "type": {
                    "type": "list",
                    "element-id": 3,
                    "element": {
                        "type": "struct",
                        "fields": [
                            {
                                "id": 4,
                                "name": "price",
                                "type": "decimal(10, 2)",
                                "required": False,
                            }
                        ],
                    },
                    "element-required": True,
                },
                "required": False,
            },
            {
                "id": 2,
                "name": "attrs",
                "type": {
                    "type": "map",
                    "key-id": 5,
                    "key": "string",
                    "value-id": 6,
                    "value": {
                        "type": "struct",
                        "fields": [
                            {
                                "id": 7,
                                "name": "score",
                                "type": "long",
                                "required": False,
                            }
                        ],
                    },
                    "value-required": False,
                },
                "required": False,
            },
        ]
    }

    flat = _flatten_schema(schema)

    assert flat[4]["name"] == "items.element.price"
    assert flat[5]["name"] == "attrs.key"
    assert flat[7]["name"] == "attrs.value.score"


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
