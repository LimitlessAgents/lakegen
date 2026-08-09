"""Tests for CatalogService (add / list / get / delete / require)."""

import json
from unittest.mock import MagicMock

import pytest

from lakegen.core.catalog.model import RestCatalogSpec
from lakegen.core.catalog.service import CatalogService
from lakegen.core.connection.registry import ConnectionRegistry
from lakegen.core.credential import json_store
from lakegen.core.credential.model import KEYRING_PLACEHOLDER
from lakegen.core.credential.store import get_connection_metadata, list_connections
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode


@pytest.fixture()
def cred_file(tmp_path, monkeypatch):
    cred = tmp_path / "credentials.json"
    cred.write_text(json.dumps({}))
    cred.chmod(0o600)
    monkeypatch.setattr(json_store, "CREDENTIALS_PATH", str(cred))
    monkeypatch.setattr(json_store, "_path", lambda: str(cred))
    return cred


@pytest.fixture()
def fake_catalog():
    catalog = MagicMock()
    catalog.connect.return_value = catalog
    return catalog


@pytest.fixture()
def service(cred_file, fake_catalog, monkeypatch):
    monkeypatch.setattr(
        "lakegen.core.connection.registry.get_catalog_instance",
        lambda spec: fake_catalog,
    )
    return CatalogService(registry=ConnectionRegistry())


def _rest_spec(name: str = "prod") -> RestCatalogSpec:
    return RestCatalogSpec(
        lakehouse="iceberg",
        catalog_type="rest",
        name=name,
        warehouse=f"s3://{name}",
        rest_catalog_url="http://catalog.example",
    )


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


def test_add_persists_and_opens(service):
    info = service.add(_rest_spec("prod"))

    assert info.name == "prod"
    assert info.connected is True
    assert info.warehouse == "s3://prod"
    assert "prod" in list_connections("catalog")
    assert "prod" in service._registry.list_open("catalog")


def test_add_duplicate_raises(service):
    service.add(_rest_spec("prod"))
    with pytest.raises(BaseError) as exc_info:
        service.add(_rest_spec("prod"))
    assert exc_info.value.code == ErrorCode.ALREADY_EXISTS


def test_list_includes_connected_flag(service):
    service.add(_rest_spec("prod"))
    service._registry.close_connection("catalog", "prod")
    json_store.store(
        "catalog",
        "dev",
        {
            "lakehouse": "iceberg",
            "catalog_type": "rest",
            "warehouse": "s3://dev",
        },
    )

    by_name = {row.name: row for row in service.list()}
    assert by_name["prod"].connected is False
    assert by_name["prod"].catalog_type == "rest"
    assert by_name["dev"].connected is False
    assert by_name["dev"].warehouse == "s3://dev"


def test_list_empty(service):
    assert service.list() == []


def test_delete_closes_and_removes(service, fake_catalog):
    service.add(_rest_spec("prod"))
    service.delete("prod")

    fake_catalog.close.assert_called_once()
    assert "prod" not in list_connections("catalog")
    assert "prod" not in service._registry.list_open("catalog")
    with pytest.raises(BaseError) as exc_info:
        service.get("prod")
    assert exc_info.value.code == ErrorCode.NOT_FOUND


def test_delete_missing_raises(service):
    with pytest.raises(BaseError) as exc_info:
        service.delete("ghost")
    assert exc_info.value.code == ErrorCode.NOT_FOUND


def test_require_and_exists(service):
    assert service.exists("prod") is False
    with pytest.raises(BaseError, match="catalog_name is required"):
        service.require("")
    with pytest.raises(BaseError, match="not registered"):
        service.require("prod")

    service.add(_rest_spec("prod"))
    assert service.exists("prod") is True
    service.require("prod")  # does not raise
