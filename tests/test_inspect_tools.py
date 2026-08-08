"""Tests for describe_table / inspect_* tool handlers."""

from unittest.mock import MagicMock

import pytest

from lakegen.tool.iceberg.describe_table_tool import (
    DescribeTableArguments,
    describe_table,
)
from lakegen.tool.iceberg.inspect_partitions_tool import (
    InspectPartitionsArguments,
    inspect_partitions,
)
from lakegen.tool.iceberg.inspect_snapshots_tool import (
    InspectSnapshotsArguments,
    inspect_snapshots,
)


@pytest.fixture()
def fake_catalog(monkeypatch):
    catalog = MagicMock()
    conreg = MagicMock()
    conreg.get_connection.return_value = catalog

    import lakegen.tool.iceberg.describe_table_tool as describe_mod
    import lakegen.tool.iceberg.inspect_partitions_tool as partitions_mod
    import lakegen.tool.iceberg.inspect_snapshots_tool as snapshots_mod

    monkeypatch.setattr(describe_mod, "conreg", conreg)
    monkeypatch.setattr(snapshots_mod, "conreg", conreg)
    monkeypatch.setattr(partitions_mod, "conreg", conreg)
    return catalog, conreg


def test_describe_table_delegates_to_get_table_metadata(fake_catalog):
    catalog, conreg = fake_catalog
    catalog.get_table_metadata.return_value = {
        "name": "sales.orders",
        "location": "s3://wh/sales/orders",
        "schema": {"id": "long"},
    }

    result = describe_table(
        DescribeTableArguments(name="prod", table="sales.orders")
    )

    conreg.get_connection.assert_called_with("catalog", "prod")
    catalog.get_table_metadata.assert_called_once_with("sales.orders")
    assert result["schema"] == {"id": "long"}


def test_inspect_snapshots_delegates(fake_catalog):
    catalog, _ = fake_catalog
    catalog.inspect_snapshots.return_value = [{"snapshot_id": 1}]

    result = inspect_snapshots(
        InspectSnapshotsArguments(name="prod", table="sales.orders")
    )

    catalog.inspect_snapshots.assert_called_once_with("sales.orders")
    assert result == [{"snapshot_id": 1}]


def test_inspect_partitions_delegates(fake_catalog):
    catalog, _ = fake_catalog
    catalog.inspect_partitions.return_value = [{"record_count": 10}]

    result = inspect_partitions(
        InspectPartitionsArguments(name="prod", table="sales.orders")
    )

    catalog.inspect_partitions.assert_called_once_with("sales.orders")
    assert result == [{"record_count": 10}]
