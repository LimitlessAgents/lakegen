"""Tests for IcebergCatalog output normalization.

PyIceberg returns identifiers as tuples; the catalog layer must convert them
to dotted strings so tool outputs are JSON-serializable.
"""

from unittest.mock import MagicMock, patch

import pytest

from lakegen.core.catalog.iceberg import IcebergCatalog
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode


def _make_catalog():
    """Return an IcebergCatalog with a mocked PyIceberg backend."""
    spec = MagicMock()
    spec.name = "test-catalog"
    spec.catalog_type = "rest"
    spec.iceberg_kwargs.return_value = ("test-catalog", {})

    catalog = IcebergCatalog(spec)
    catalog.catalog = MagicMock()
    return catalog


# ---------------------------------------------------------------------------
# list_namespaces
# ---------------------------------------------------------------------------

def test_list_namespaces_tuples_become_dotted_strings():
    cat = _make_catalog()
    cat.catalog.list_namespaces.return_value = [("sales",), ("finance", "q1")]
    result = cat.list_namespaces()
    assert result == ["sales", "finance.q1"]


def test_list_namespaces_empty():
    cat = _make_catalog()
    cat.catalog.list_namespaces.return_value = []
    assert cat.list_namespaces() == []


def test_list_namespaces_error_wrapped():
    cat = _make_catalog()
    cat.catalog.list_namespaces.side_effect = RuntimeError("network error")
    with pytest.raises(BaseError) as exc_info:
        cat.list_namespaces()
    assert exc_info.value.code == ErrorCode.INTERNAL


# ---------------------------------------------------------------------------
# list_tables
# ---------------------------------------------------------------------------

def test_list_tables_tuples_become_dotted_strings():
    cat = _make_catalog()
    cat.catalog.list_tables.return_value = [("sales", "orders"), ("sales", "items")]
    result = cat.list_tables("sales")
    assert result == ["sales.orders", "sales.items"]
    cat.catalog.list_tables.assert_called_once_with(namespace="sales")


def test_list_tables_empty():
    cat = _make_catalog()
    cat.catalog.list_tables.return_value = []
    assert cat.list_tables("sales") == []


def test_list_tables_error_wrapped():
    cat = _make_catalog()
    cat.catalog.list_tables.side_effect = RuntimeError("timeout")
    with pytest.raises(BaseError) as exc_info:
        cat.list_tables("sales")
    assert exc_info.value.code == ErrorCode.INTERNAL


# ---------------------------------------------------------------------------
# get_table_metadata
# ---------------------------------------------------------------------------

def _mock_field(name, field_type_str):
    f = MagicMock()
    f.name = name
    f.field_type = field_type_str
    return f


def test_get_table_metadata_returns_plain_dict():
    cat = _make_catalog()
    mock_table = MagicMock()
    mock_table.name.return_value = "sales.orders"
    mock_table.location.return_value = "s3://bucket/sales/orders"
    mock_table.schema.return_value.fields = [
        _mock_field("id", "long"),
        _mock_field("amount", "double"),
    ]
    cat.catalog.load_table.return_value = mock_table

    result = cat.get_table_metadata("sales.orders")
    assert result["name"] == "sales.orders"
    assert result["location"] == "s3://bucket/sales/orders"
    assert result["schema"] == {"id": "long", "amount": "double"}


def test_get_table_metadata_is_json_serializable():
    import json

    cat = _make_catalog()
    mock_table = MagicMock()
    mock_table.name.return_value = "ns.tbl"
    mock_table.location.return_value = "s3://x/y"
    mock_table.schema.return_value.fields = [_mock_field("col", "string")]
    cat.catalog.load_table.return_value = mock_table

    result = cat.get_table_metadata("ns.tbl")
    # Must not raise.
    serialized = json.dumps(result)
    assert "ns.tbl" in serialized


def test_get_table_metadata_error_wrapped():
    cat = _make_catalog()
    cat.catalog.load_table.side_effect = RuntimeError("not found")
    with pytest.raises(BaseError) as exc_info:
        cat.get_table_metadata("ghost.table")
    assert exc_info.value.code == ErrorCode.INTERNAL


# ---------------------------------------------------------------------------
# inspect_snapshots / inspect_partitions
# ---------------------------------------------------------------------------

def test_inspect_snapshots_returns_json_rows():
    import pyarrow as pa
    from datetime import datetime

    cat = _make_catalog()
    mock_table = MagicMock()
    mock_table.inspect.snapshots.return_value = pa.table(
        {
            "committed_at": pa.array(
                [datetime(2024, 3, 15, 15, 1, 25)],
                type=pa.timestamp("ms"),
            ),
            "snapshot_id": [805611270568163028],
            "parent_id": pa.array([None], type=pa.int64()),
            "operation": ["append"],
            "summary": pa.array(
                [{"added-records": "3"}],
                type=pa.map_(pa.string(), pa.string()),
            ),
        }
    )
    cat.catalog.load_table.return_value = mock_table

    result = cat.inspect_snapshots("sales.orders")
    assert result == [
        {
            "committed_at": "2024-03-15T15:01:25",
            "snapshot_id": 805611270568163028,
            "parent_id": None,
            "operation": "append",
            "summary": {"added-records": "3"},
        }
    ]
    cat.catalog.load_table.assert_called_once_with("sales.orders")


def test_inspect_partitions_returns_json_rows():
    import pyarrow as pa
    from datetime import date

    cat = _make_catalog()
    mock_table = MagicMock()
    mock_table.inspect.partitions.return_value = pa.table(
        {
            "partition": [{"dt_day": date(2021, 2, 1)}],
            "record_count": [10],
            "file_count": [2],
            "total_data_file_size_in_bytes": [1024],
        }
    )
    cat.catalog.load_table.return_value = mock_table

    result = cat.inspect_partitions("sales.orders")
    assert result == {
        "rows": [
            {
                "partition": {"dt_day": "2021-02-01"},
                "record_count": 10,
                "file_count": 2,
                "total_data_file_size_in_bytes": 1024,
            }
        ],
        "truncated": False,
        "total": 1,
    }
    mock_table.inspect.partitions.assert_called_once_with(snapshot_id=None)


def test_inspect_partitions_passes_snapshot_id():
    import pyarrow as pa

    cat = _make_catalog()
    mock_table = MagicMock()
    mock_table.inspect.partitions.return_value = pa.table({"record_count": [1]})
    cat.catalog.load_table.return_value = mock_table

    cat.inspect_partitions("sales.orders", snapshot_id=123)

    mock_table.inspect.partitions.assert_called_once_with(snapshot_id=123)


def test_inspect_history_returns_limited_rows():
    import pyarrow as pa

    cat = _make_catalog()
    mock_table = MagicMock()
    mock_table.inspect.history.return_value = pa.table(
        {"snapshot_id": list(range(3))}
    )
    cat.catalog.load_table.return_value = mock_table

    result = cat.inspect_history("sales.orders", limit=2)

    assert result["truncated"] is True
    assert result["total"] == 3
    assert len(result["rows"]) == 2


def test_inspect_files_passes_snapshot_id():
    import pyarrow as pa

    cat = _make_catalog()
    mock_table = MagicMock()
    mock_table.inspect.files.return_value = pa.table({"file_path": ["s3://x"]})
    cat.catalog.load_table.return_value = mock_table

    cat.inspect_files("sales.orders", snapshot_id=999)

    mock_table.inspect.files.assert_called_once_with(snapshot_id=999)


def test_inspect_metadata_log_delegates_to_pyiceberg():
    import pyarrow as pa

    cat = _make_catalog()
    mock_table = MagicMock()
    mock_table.inspect.metadata_log_entries.return_value = pa.table(
        {"file": ["s3://wh/meta.json"]}
    )
    cat.catalog.load_table.return_value = mock_table

    result = cat.inspect_metadata_log("sales.orders")

    assert result["rows"] == [{"file": "s3://wh/meta.json"}]
    assert result["truncated"] is False


def test_inspect_snapshots_error_wrapped():
    cat = _make_catalog()
    cat.catalog.load_table.side_effect = RuntimeError("boom")
    with pytest.raises(BaseError) as exc_info:
        cat.inspect_snapshots("sales.orders")
    assert exc_info.value.code == ErrorCode.INTERNAL


def test_inspect_partitions_error_wrapped():
    cat = _make_catalog()
    cat.catalog.load_table.side_effect = RuntimeError("boom")
    with pytest.raises(BaseError) as exc_info:
        cat.inspect_partitions("sales.orders")
    assert exc_info.value.code == ErrorCode.INTERNAL
