from unittest.mock import MagicMock

import pytest

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.core.persistence import PostgresPersistence
from lakegen.core.persistence.repository.catalog_repository import (
    CatalogRepository,
)


def _rest_spec() -> dict[str, object]:
    return {
        "lakehouse": "iceberg",
        "catalog_type": "rest",
        "name": "production",
        "warehouse": "s3://warehouse",
        "rest_catalog_url": "https://catalog.example.com",
        "token": "secret-token",
    }


def _sql_spec() -> dict[str, object]:
    return {
        "lakehouse": "iceberg",
        "catalog_type": "sql",
        "name": "warehouse-db",
        "warehouse": "s3://warehouse",
        "database_type": "postgresql",
        "host": "db.example.com",
        "port": 5432,
        "username": "lakegen",
        "password": "database-secret",
        "database": "iceberg",
    }


def test_create_stores_config_and_credentials_in_one_row() -> None:
    database = MagicMock(spec=PostgresPersistence)

    CatalogRepository(database).create(_rest_spec())

    database.insert.assert_called_once()
    table_name, row = database.insert.call_args.args
    assert table_name == "catalogs"
    assert row["name"] == "production"
    assert row["lakehouse"] == "iceberg"
    assert row["catalog_type"] == "rest"
    assert row["config"].obj == {
        "rest_catalog_url": "https://catalog.example.com",
        "warehouse": "s3://warehouse",
    }
    assert row["credentials"].obj == {"token": "secret-token"}


def test_create_keeps_sql_password_out_of_public_config() -> None:
    database = MagicMock(spec=PostgresPersistence)

    CatalogRepository(database).create(_sql_spec())

    row = database.insert.call_args.args[1]
    assert "password" not in row["config"].obj
    assert row["config"].obj["username"] == "lakegen"
    assert row["credentials"].obj == {"password": "database-secret"}


def test_get_merges_config_and_credentials() -> None:
    database = MagicMock(spec=PostgresPersistence)
    database.fetch_one.return_value = {
        "name": "production",
        "lakehouse": "iceberg",
        "catalog_type": "rest",
        "config": {
            "warehouse": "s3://warehouse",
            "rest_catalog_url": "https://catalog.example.com",
        },
        "credentials": {"token": "secret-token"},
    }

    assert CatalogRepository(database).get("production") == _rest_spec()


def test_get_missing_raises_not_found() -> None:
    database = MagicMock(spec=PostgresPersistence)
    database.fetch_one.return_value = None

    with pytest.raises(BaseError) as exc_info:
        CatalogRepository(database).get("missing")

    assert exc_info.value.code == ErrorCode.NOT_FOUND


def test_list_metadata_omits_credentials() -> None:
    database = MagicMock(spec=PostgresPersistence)
    rows = [
        {
            "name": "production",
            "lakehouse": "iceberg",
            "catalog_type": "rest",
            "config": {"warehouse": "s3://warehouse"},
        }
    ]
    database.fetch_all.return_value = rows

    assert CatalogRepository(database).list_metadata() == [
        {
            "name": "production",
            "lakehouse": "iceberg",
            "catalog_type": "rest",
            "warehouse": "s3://warehouse",
        }
    ]
    database.fetch_all.assert_called_once()
