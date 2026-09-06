"""Tests for describe_table / inspect_* tool handlers."""

from unittest.mock import MagicMock

import pytest

from lakegen.tool.iceberg.describe_table_tool import describe_table
from lakegen.tool.iceberg.inspect_entries_tool import inspect_entries
from lakegen.tool.iceberg.inspect_files_tool import inspect_files
from lakegen.tool.iceberg.inspect_history_tool import inspect_history
from lakegen.tool.iceberg.inspect_manifests_tool import inspect_manifests
from lakegen.tool.iceberg.inspect_metadata_log_tool import inspect_metadata_log
from lakegen.tool.iceberg.inspect_partitions_tool import inspect_partitions
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


def test_inspect_partitions_delegates(fake_catalog):
    catalog = fake_catalog
    payload = {"rows": [{"record_count": 10}], "truncated": False, "total": 1}
    catalog.inspect_partitions.return_value = payload

    result = inspect_partitions(
        TimeTravelInspectArguments(
            name="prod",
            table="sales.orders",
            snapshot_id=42,
            limit=25,
        ),
        catalog,
    )

    catalog.inspect_partitions.assert_called_once_with(
        "sales.orders",
        snapshot_id=42,
        limit=25,
    )
    assert result == payload


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


@pytest.mark.parametrize(
    ("tool", "catalog_method"),
    [
        (inspect_files, "inspect_files"),
        (inspect_entries, "inspect_entries"),
    ],
)
def test_time_travel_inspect_tools_delegate(fake_catalog, tool, catalog_method):
    catalog = fake_catalog
    payload = {"rows": [{"file_path": "s3://x"}], "truncated": False, "total": 1}
    getattr(catalog, catalog_method).return_value = payload

    result = tool(
        TimeTravelInspectArguments(
            name="prod",
            table="sales.orders",
            snapshot_id=999,
            limit=10,
        ),
        catalog,
    )

    getattr(catalog, catalog_method).assert_called_once_with(
        "sales.orders",
        snapshot_id=999,
        limit=10,
    )
    assert result == payload
