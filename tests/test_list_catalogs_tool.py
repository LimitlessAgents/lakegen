"""Tests for list_catalogs tool and related connection helpers."""

import json

import pytest

from lakegen.core.connection.registry import ConnectionRegistry
from lakegen.core.credential import json_store
from lakegen.core.credential.model import KEYRING_PLACEHOLDER
from lakegen.core.credential.store import get_connection_metadata
from lakegen.tool.iceberg.list_catalogs_tool import (
    ListCatalogsArguments,
    list_catalogs,
)


@pytest.fixture()
def cred_file(tmp_path, monkeypatch):
    cred = tmp_path / "credentials.json"
    cred.write_text(json.dumps({}))
    cred.chmod(0o600)
    monkeypatch.setattr(json_store, "CREDENTIALS_PATH", str(cred))
    monkeypatch.setattr(json_store, "_path", lambda: str(cred))
    return cred


def test_get_connection_metadata_omits_secrets(cred_file):
    json_store.store(
        "catalog",
        "prod",
        {
            "lakehouse": "iceberg",
            "catalog_type": "rest",
            "warehouse": "s3://wh",
            "access_key": KEYRING_PLACEHOLDER,
            "token": KEYRING_PLACEHOLDER,
        },
    )

    meta = get_connection_metadata("catalog", "prod")
    assert meta == {
        "lakehouse": "iceberg",
        "catalog_type": "rest",
        "warehouse": "s3://wh",
    }


def test_list_open_returns_cached_names():
    reg = ConnectionRegistry()
    reg._open["catalog"]["prod"] = object()
    reg._open["catalog"]["dev"] = object()
    assert set(reg.list_open("catalog")) == {"prod", "dev"}


def test_list_catalogs_includes_connected_flag(cred_file, monkeypatch):
    from lakegen.tool.iceberg import list_catalogs_tool

    json_store.store(
        "catalog",
        "prod",
        {
            "lakehouse": "iceberg",
            "catalog_type": "glue",
            "warehouse": "s3://prod",
            "secret_key": KEYRING_PLACEHOLDER,
        },
    )
    json_store.store(
        "catalog",
        "dev",
        {
            "lakehouse": "iceberg",
            "catalog_type": "rest",
            "warehouse": "s3://dev",
        },
    )

    fake_reg = ConnectionRegistry()
    fake_reg._open["catalog"]["prod"] = object()
    monkeypatch.setattr(list_catalogs_tool, "conreg", fake_reg)

    result = list_catalogs(ListCatalogsArguments())
    by_name = {row["name"]: row for row in result}

    assert by_name["prod"] == {
        "name": "prod",
        "connected": True,
        "lakehouse": "iceberg",
        "catalog_type": "glue",
        "warehouse": "s3://prod",
    }
    assert by_name["dev"] == {
        "name": "dev",
        "connected": False,
        "lakehouse": "iceberg",
        "catalog_type": "rest",
        "warehouse": "s3://dev",
    }


def test_list_catalogs_empty(cred_file, monkeypatch):
    from lakegen.tool.iceberg import list_catalogs_tool

    monkeypatch.setattr(list_catalogs_tool, "conreg", ConnectionRegistry())
    assert list_catalogs(ListCatalogsArguments()) == []
