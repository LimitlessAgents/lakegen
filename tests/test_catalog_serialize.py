"""Tests for Arrow → JSON-native conversion used by inspect tools."""

import json
from datetime import date, datetime

import pyarrow as pa

from lakegen.core.catalog.serialize import (
    DEFAULT_INSPECT_LIMIT,
    arrow_table_to_rows,
    limit_inspect_rows,
)


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


def test_limit_inspect_rows_uses_default():
    rows = [{"id": index} for index in range(DEFAULT_INSPECT_LIMIT + 5)]
    result = limit_inspect_rows(rows)
    assert result["truncated"] is True
    assert result["total"] == DEFAULT_INSPECT_LIMIT + 5
    assert len(result["rows"]) == DEFAULT_INSPECT_LIMIT


def test_limit_inspect_rows_custom_limit():
    rows = [{"id": 1}, {"id": 2}, {"id": 3}]
    result = limit_inspect_rows(rows, limit=2)
    assert result == {
        "rows": [{"id": 1}, {"id": 2}],
        "truncated": True,
        "total": 3,
    }


def test_limit_inspect_rows_not_truncated():
    rows = [{"id": 1}]
    result = limit_inspect_rows(rows, limit=10)
    assert result == {
        "rows": [{"id": 1}],
        "truncated": False,
        "total": 1,
    }
