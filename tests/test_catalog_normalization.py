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
# load_table
# ---------------------------------------------------------------------------

def _mock_field(name, field_type_str):
    f = MagicMock()
    f.name = name
    f.field_type = field_type_str
    return f


def test_load_table_returns_plain_dict():
    cat = _make_catalog()
    mock_table = MagicMock()
    mock_table.name.return_value = "sales.orders"
    mock_table.location.return_value = "s3://bucket/sales/orders"
    mock_table.schema.return_value.fields = [
        _mock_field("id", "long"),
        _mock_field("amount", "double"),
    ]
    cat.catalog.load_table.return_value = mock_table

    result = cat.load_table("sales.orders")
    assert result["name"] == "sales.orders"
    assert result["location"] == "s3://bucket/sales/orders"
    assert result["schema"] == {"id": "long", "amount": "double"}


def test_load_table_is_json_serializable():
    import json

    cat = _make_catalog()
    mock_table = MagicMock()
    mock_table.name.return_value = "ns.tbl"
    mock_table.location.return_value = "s3://x/y"
    mock_table.schema.return_value.fields = [_mock_field("col", "string")]
    cat.catalog.load_table.return_value = mock_table

    result = cat.load_table("ns.tbl")
    # Must not raise.
    serialized = json.dumps(result)
    assert "ns.tbl" in serialized


def test_load_table_error_wrapped():
    cat = _make_catalog()
    cat.catalog.load_table.side_effect = RuntimeError("not found")
    with pytest.raises(BaseError) as exc_info:
        cat.load_table("ghost.table")
    assert exc_info.value.code == ErrorCode.INTERNAL
