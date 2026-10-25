"""Tests for describe_table / inspect_* tool handlers."""

from unittest.mock import MagicMock

import pytest

from lakegen.tool.iceberg.describe_table_tool import describe_table
from lakegen.tool.iceberg.inspect_entries_tool import inspect_entries
from lakegen.tool.iceberg.inspect_files_tool import inspect_files
from lakegen.tool.iceberg.inspect_history_tool import inspect_history
from lakegen.tool.iceberg.inspect_manifests_tool import inspect_manifests
from lakegen.tool.iceberg.inspect_metadata_log_tool import inspect_metadata_log
from lakegen.tool.iceberg.inspect_refs_tool import inspect_refs
from lakegen.tool.iceberg.inspect_snapshots_tool import inspect_snapshots
from lakegen.tool.iceberg.model import (
    CatalogTableArguments,
    InspectTableArguments,
    TimeTravelInspectArguments,
)


@pytest.fixture()
def fake_catalog():
    return MagicMock()


def test_describe_table_delegates_to_get_table_metadata(fake_catalog):
    catalog = fake_catalog
    catalog.get_table_metadata.return_value = {
        "name": "sales.orders",
        "location": "s3://wh/sales/orders",
        "schema": {"id": "long"},
    }

    result = describe_table(
        CatalogTableArguments(name="prod", table="sales.orders"),
        catalog,
    )

    catalog.get_table_metadata.assert_called_once_with("sales.orders")
    assert result["schema"] == {"id": "long"}


def test_inspect_snapshots_delegates(fake_catalog):
    catalog = fake_catalog
    catalog.inspect_snapshots.return_value = [{"snapshot_id": 1}]

    result = inspect_snapshots(
        CatalogTableArguments(name="prod", table="sales.orders"),
        catalog,
    )

    catalog.inspect_snapshots.assert_called_once_with("sales.orders")
    assert result == [{"snapshot_id": 1}]


@pytest.mark.parametrize(
    ("tool", "catalog_method"),
    [
        (inspect_history, "inspect_history"),
        (inspect_refs, "inspect_refs"),
        (inspect_manifests, "inspect_manifests"),
        (inspect_metadata_log, "inspect_metadata_log"),
    ],
)
def test_advanced_inspect_tools_delegate(fake_catalog, tool, catalog_method):
    catalog = fake_catalog
    payload = {"rows": [], "truncated": False, "total": 0}
    getattr(catalog, catalog_method).return_value = payload

    result = tool(
        InspectTableArguments(name="prod", table="sales.orders", limit=50),
        catalog,
    )

    getattr(catalog, catalog_method).assert_called_once_with(
        "sales.orders",
        limit=50,
    )
    assert result == payload


def test_inspect_files_fetches_all_rows_and_limits_in_tool(fake_catalog):
    catalog = fake_catalog
    catalog.inspect_files.return_value = [
        {"file_path": "s3://a"},
        {"file_path": "s3://b"},
    ]

    result = inspect_files(
        TimeTravelInspectArguments(
            name="prod",
            table="sales.orders",
            snapshot_id=999,
            limit=1,
        ),
        catalog,
    )

    catalog.inspect_files.assert_called_once_with(
        "sales.orders",
        snapshot_id=999,
    )
    assert result == {
        "rows": [{"file_path": "s3://a"}],
        "truncated": True,
        "total": 2,
    }


def test_inspect_entries_delegates(fake_catalog):
    catalog = fake_catalog
    payload = {"rows": [{"file_path": "s3://x"}], "truncated": False, "total": 1}
    catalog.inspect_entries.return_value = payload

    result = inspect_entries(
        TimeTravelInspectArguments(
            name="prod",
            table="sales.orders",
            snapshot_id=999,
            limit=10,
        ),
        catalog,
    )

    catalog.inspect_entries.assert_called_once_with(
        "sales.orders",
        snapshot_id=999,
        limit=10,
    )
    assert result == payload
