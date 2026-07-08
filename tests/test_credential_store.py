"""Tests for credential storage: json_store, keyring_store, and store facade."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lakegen.core.credential import json_store, keyring_store
from lakegen.core.credential.model import KEYRING_PLACEHOLDER
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def cred_file(tmp_path, monkeypatch):
    """Point json_store at a fresh temp credentials file."""
    cred = tmp_path / "credentials.json"
    cred.write_text(json.dumps({}))
    cred.chmod(0o600)
    monkeypatch.setattr(json_store, "CREDENTIALS_PATH", str(cred))
    # Also patch _path() return value since it expands CREDENTIALS_PATH.
    monkeypatch.setattr(json_store, "_path", lambda: str(cred))
    return cred


# ---------------------------------------------------------------------------
# json_store: basic CRUD
# ---------------------------------------------------------------------------

def test_store_and_load(cred_file):
    json_store.store("catalog", "prod", {"host": "localhost", "port": 5432})
    result = json_store.load("catalog", "prod")
    assert result == {"host": "localhost", "port": 5432}


def test_load_not_found_raises(cred_file):
    with pytest.raises(BaseError) as exc_info:
        json_store.load("catalog", "ghost")
    assert exc_info.value.code == ErrorCode.NOT_FOUND


def test_store_multiple_connections(cred_file):
    json_store.store("catalog", "a", {"x": 1})
    json_store.store("catalog", "b", {"x": 2})
    assert json_store.load("catalog", "a") == {"x": 1}
    assert json_store.load("catalog", "b") == {"x": 2}


def test_store_overwrites(cred_file):
    json_store.store("catalog", "prod", {"v": 1})
    json_store.store("catalog", "prod", {"v": 2})
    assert json_store.load("catalog", "prod")["v"] == 2


def test_delete_removes_entry(cred_file):
    json_store.store("catalog", "prod", {"x": 1})
    json_store.delete("catalog", "prod")
    with pytest.raises(BaseError) as exc_info:
        json_store.load("catalog", "prod")
    assert exc_info.value.code == ErrorCode.NOT_FOUND


def test_delete_missing_is_noop(cred_file):
    json_store.delete("catalog", "ghost")  # must not raise


def test_list_by_kind(cred_file):
    json_store.store("catalog", "a", {})
    json_store.store("catalog", "b", {})
    names = json_store.list_connections("catalog")
    assert set(names) == {"a", "b"}


def test_list_all(cred_file):
    json_store.store("catalog", "a", {})
    json_store.store("database", "db1", {})
    result = json_store.list_connections()
    assert "a" in result["catalog"]
    assert "db1" in result["database"]


# ---------------------------------------------------------------------------
# json_store: atomic write
# ---------------------------------------------------------------------------

def test_atomic_write_produces_valid_json(cred_file):
    json_store.store("catalog", "prod", {"key": "value"})
    raw = cred_file.read_text()
    parsed = json.loads(raw)
    assert parsed["catalog"]["prod"]["key"] == "value"


def test_atomic_write_permissions(cred_file):
    json_store.store("catalog", "prod", {"k": "v"})
    mode = oct(os.stat(str(cred_file)).st_mode & 0o777)
    assert mode == oct(0o600)


def test_atomic_write_no_tmp_file_left(cred_file):
    json_store.store("catalog", "prod", {"k": "v"})
    parent = cred_file.parent
    tmp_files = list(parent.glob("*.tmp"))
    assert tmp_files == []


# ---------------------------------------------------------------------------
# json_store: corrupt file recovery
# ---------------------------------------------------------------------------

def test_read_empty_file_recreates_and_returns_empty_dict(cred_file):
    cred_file.write_text("")
    from lakegen.core.credential.json_store import _read

    result = _read(str(cred_file))
    assert result == {}
    assert json.loads(cred_file.read_text()) == {}


def test_read_corrupt_json_repairs_and_persists(cred_file):
    cred_file.write_text('{"catalog": {"prod": {"host": "localhost"')
    from lakegen.core.credential.json_store import _read

    result = _read(str(cred_file))
    assert isinstance(result, dict)
    # Repaired content should be valid JSON on disk.
    assert json.loads(cred_file.read_text()) == result


def test_store_succeeds_after_empty_file(cred_file):
    cred_file.write_text("")
    json_store.store("catalog", "prod", {"host": "localhost"})
    assert json_store.load("catalog", "prod") == {"host": "localhost"}


# ---------------------------------------------------------------------------
# store facade: keyring + JSON interaction
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_keyring(monkeypatch):
    """Replace keyring backend with an in-memory dict."""
    vault: dict[str, dict[str, str]] = {}

    class _FakeKeyring:
        @staticmethod
        def set_password(service, key, value):
            vault.setdefault(service, {})[key] = value

        @staticmethod
        def get_password(service, key):
            return vault.get(service, {}).get(key)

        @staticmethod
        def delete_password(service, key):
            vault.get(service, {}).pop(key, None)

    monkeypatch.setattr(keyring_store, "_backend", _FakeKeyring)
    return vault


def test_store_credentials_separates_secrets(cred_file, fake_keyring):
    from lakegen.core.credential.store import get_credentials, store_credentials

    creds = {
        "name": "prod",
        "access_key": "AKID",
        "secret_key": "SECRET",
        "region": "us-east-1",
    }
    store_credentials("catalog", "prod", creds)

    raw = json.loads(cred_file.read_text())
    stored_entry = raw["catalog"]["prod"]
    # Non-secret fields should be in JSON.
    assert stored_entry["region"] == "us-east-1"
    # Secrets should be placeholders in JSON.
    assert stored_entry["access_key"] == KEYRING_PLACEHOLDER
    assert stored_entry["secret_key"] == KEYRING_PLACEHOLDER


def test_get_credentials_restores_secrets(cred_file, fake_keyring):
    from lakegen.core.credential.store import get_credentials, store_credentials

    creds = {"name": "prod", "access_key": "AKID", "region": "us-east-1"}
    store_credentials("catalog", "prod", creds)

    loaded = get_credentials("catalog", "prod")
    assert loaded["access_key"] == "AKID"
    assert loaded["region"] == "us-east-1"


def test_store_credentials_rolls_back_keyring_on_json_failure(cred_file, fake_keyring, monkeypatch):
    """If the JSON write fails after a successful keyring write, keyring is rolled back."""
    from lakegen.core.credential.store import store_credentials

    original_write = json_store._write

    call_count = {"n": 0}

    def _failing_write(path, data):
        call_count["n"] += 1
        raise BaseError(ErrorCode.JSON, "disk full")

    monkeypatch.setattr(json_store, "_write", _failing_write)

    creds = {"name": "prod", "access_key": "AKID"}
    with pytest.raises(BaseError) as exc_info:
        store_credentials("catalog", "prod", creds)

    assert exc_info.value.code == ErrorCode.JSON
    # Keyring should be clean — the secret was rolled back.
    from lakegen.core.credential.model import SERVICE_NAME
    assert keyring_store._backend.get_password(SERVICE_NAME, "catalog/prod/access_key") is None


def test_store_credentials_json_fallback_when_keyring_unavailable(cred_file, monkeypatch):
    """When keyring is unavailable, all creds land in the JSON file."""
    from lakegen.core.credential import keyring_store as _ks
    from lakegen.core.credential.store import store_credentials, get_credentials
    from lakegen.core.error.code import ErrorCode

    def _failing_store(connection_name, secrets):
        raise BaseError(ErrorCode.KEYRING, "no keyring")

    monkeypatch.setattr(_ks, "store", _failing_store)

    creds = {"name": "prod", "access_key": "AKID", "region": "us-east-1"}
    store_credentials("catalog", "prod", creds)

    raw = json.loads(cred_file.read_text())
    # When keyring is unavailable, secrets must be stored in JSON directly.
    assert raw["catalog"]["prod"]["access_key"] == "AKID"
