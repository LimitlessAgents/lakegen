"""Tests for catalog lifecycle orchestration."""

from unittest.mock import MagicMock

import pytest

from lakegen.core.catalog.model import RestCatalogSpec
from lakegen.core.catalog.service import CatalogService
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.core.persistence.repository.catalog_repository import CatalogRepository


@pytest.fixture()
def repository() -> MagicMock:
    repository = MagicMock(spec=CatalogRepository)
    repository.exists.return_value = False
    return repository


@pytest.fixture()
def catalog() -> MagicMock:
    instance = MagicMock()
    instance.connect.return_value = instance
    return instance


@pytest.fixture()
def service(repository, catalog) -> CatalogService:
    return CatalogService(repository=repository, factory=lambda spec: catalog)


def _rest_spec(name: str = "prod") -> RestCatalogSpec:
    return RestCatalogSpec(
        lakehouse="iceberg",
        catalog_type="rest",
        name=name,
        warehouse=f"s3://{name}",
        rest_catalog_url="http://catalog.example",
    )


def _metadata(name: str = "prod") -> dict[str, object]:
    return {
        "name": name,
        "lakehouse": "iceberg",
        "catalog_type": "rest",
        "warehouse": f"s3://{name}",
    }


def test_add_tests_then_persists_and_caches(
    service,
    repository,
    catalog,
) -> None:
    info = service.add(_rest_spec())

    catalog.connect.assert_called_once_with()
    catalog.test_connection.assert_called_once_with()
    repository.create.assert_called_once()
    assert repository.create.call_args.args[0]["rest_catalog_url"] == (
        "http://catalog.example"
    )
    assert service.get_connection("prod") is catalog
    assert info.connected is True


def test_add_does_not_persist_failed_connection(
    service,
    repository,
    catalog,
) -> None:
    catalog.test_connection.side_effect = BaseError(
        ErrorCode.CONNECTION_FAILED,
        "unreachable",
    )

    with pytest.raises(BaseError):
        service.add(_rest_spec())

    repository.create.assert_not_called()
    catalog.close.assert_called_once_with()


def test_add_closes_connection_when_persistence_fails(
    service,
    repository,
    catalog,
) -> None:
    repository.create.side_effect = RuntimeError("database unavailable")

    with pytest.raises(RuntimeError):
        service.add(_rest_spec())

    catalog.close.assert_called_once_with()


def test_add_duplicate_raises(service, repository, catalog) -> None:
    repository.exists.return_value = True

    with pytest.raises(BaseError) as exc_info:
        service.add(_rest_spec())

    assert exc_info.value.code == ErrorCode.ALREADY_EXISTS
    catalog.connect.assert_not_called()


def test_get_connection_rebuilds_from_repository(
    service,
    repository,
    catalog,
) -> None:
    repository.get.return_value = {
        **_metadata(),
        "rest_catalog_url": "http://catalog.example",
    }

    assert service.get_connection("prod") is catalog
    assert service.get_connection("prod") is catalog
    repository.get.assert_called_once_with("prod")
    catalog.connect.assert_called_once_with()


def test_list_reports_cache_state(service, repository, catalog) -> None:
    repository.list_metadata.return_value = [_metadata("prod"), _metadata("dev")]
    repository.get.return_value = {
        **_metadata("prod"),
        "rest_catalog_url": "http://catalog.example",
    }
    service.get_connection("prod")

    by_name = {row.name: row for row in service.list()}

    assert by_name["prod"].connected is True
    assert by_name["dev"].connected is False


def test_get_uses_public_metadata_without_loading_credentials(
    service,
    repository,
) -> None:
    repository.get_metadata.return_value = _metadata()

    info = service.get("prod")

    assert info.name == "prod"
    assert info.warehouse == "s3://prod"
    repository.get.assert_not_called()


def test_delete_removes_record_and_closes_cached_connection(
    service,
    repository,
    catalog,
) -> None:
    repository.get.return_value = {
        **_metadata(),
        "rest_catalog_url": "http://catalog.example",
    }
    repository.exists.return_value = True
    service.get_connection("prod")

    service.delete("prod")

    repository.delete.assert_called_once_with("prod")
    catalog.close.assert_called_once_with()


def test_require_missing_raises(service, repository) -> None:
    repository.exists.return_value = False

    with pytest.raises(BaseError) as exc_info:
        service.require("prod")

    assert exc_info.value.code == ErrorCode.NOT_FOUND
