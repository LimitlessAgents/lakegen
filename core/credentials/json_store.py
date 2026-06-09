"""JSON-file-backed storage for connection credentials.

The file holds one entry per connection, keyed by connection name, with each
value being a dict of ``field -> value``. Secret fields are replaced with
``KEYRING_PLACEHOLDER`` when their real values live in the keyring.

The file is expected to already exist (created during application startup);
writes to a missing file are treated as a failure rather than created here.
"""

import json
import os
from typing import Any

from core.errors.base import BaseError
from core.errors.codes import ErrorCode
from credentials.model import CREDENTIALS_PATH


def _path() -> str:
    """Absolute path to the credentials file, with ``~`` expanded."""
    return os.path.expanduser(CREDENTIALS_PATH)


def _read(path: str) -> dict[str, Any]:
    """Load the whole store. Returns ``{}`` if the file is missing."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        raise BaseError(
            ErrorCode.JSON,
            "Credentials file is corrupt.",
            cause=e,
        ) from e
    except OSError as e:
        raise BaseError(
            ErrorCode.JSON,
            "Failed to read credentials file.",
            cause=e,
        ) from e


def _write(path: str, data: dict[str, Any]) -> None:
    """Write the whole store and restrict the file to owner-only access."""
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        os.chmod(path, 0o600)
    except Exception as e:
        raise BaseError(
            ErrorCode.JSON,
            "Failed to write credentials file.",
            cause=e,
        ) from e


def store(connection_name: str, creds: dict[str, Any]) -> None:
    """Save (or overwrite) one connection's credentials. Other entries are kept."""
    path = _path()
    if not os.path.exists(path):
        raise BaseError(ErrorCode.JSON, "Credentials file does not exist.")
    data = _read(path)
    data[connection_name] = creds
    _write(path, data)

def load(connection_name: str) -> dict[str, Any]:
    """Return one connection's stored fields, or ``{}`` if it does not exist."""
    data = _read(_path()).get(connection_name, None)
    if data is None:
        raise BaseError(
            ErrorCode.JSON,
            f"No connection data found for connection_name: {connection_name}",
        )
    return data

def delete(connection_name: str) -> None:
    """Remove one connection. No-op if the connection is absent."""
    path = _path()
    if not os.path.exists(path):
        raise BaseError(ErrorCode.JSON, "Credentials file does not exist.")
    data = _read(path)
    if connection_name not in data:
        return
    del data[connection_name]
    _write(path, data)

def list() -> list[str]:
    """List all available connections."""
    return list(_read(_path()).keys())
