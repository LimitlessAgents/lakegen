"""Tests for Arrow → JSON-native conversion used by inspect tools."""

import json
from datetime import date, datetime

import pyarrow as pa

from lakegen.core.catalog.serialize import arrow_table_to_rows


def test_arrow_table_to_rows_converts_timestamps_and_maps():
    table = pa.table(
        {
            "committed_at": pa.array(
                [datetime(2024, 3, 15, 15, 1, 25)],
                type=pa.timestamp("ms"),
            ),
            "snapshot_id": [1],
            "summary": pa.array(
                [{"added-records": "3", "added-files-size": "100"}],
                type=pa.map_(pa.string(), pa.string()),
            ),
        }
    )

    rows = arrow_table_to_rows(table)
    assert rows[0]["committed_at"] == "2024-03-15T15:01:25"
    assert rows[0]["summary"] == {
        "added-records": "3",
        "added-files-size": "100",
    }
    json.dumps(rows)  # must not raise


def test_arrow_table_to_rows_converts_nested_structs_and_dates():
    table = pa.table(
        {
            "partition": [{"dt_day": date(2021, 2, 1), "region": "us"}],
            "record_count": [5],
        }
    )

    rows = arrow_table_to_rows(table)
    assert rows == [
        {
            "partition": {"dt_day": "2021-02-01", "region": "us"},
            "record_count": 5,
        }
    ]
    json.dumps(rows)


def test_arrow_table_to_rows_empty():
    table = pa.table({"snapshot_id": pa.array([], type=pa.int64())})
    assert arrow_table_to_rows(table) == []
