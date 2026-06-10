"""Read and write connection credentials in a JSON file.

Each connection is one entry in ``~/.lakegen/credentials.json``. The file must
already exist before writes (created at app startup).

Raises ``BaseError`` with code ``JSON`` or ``NOT_FOUND`` on failure.
"""

import json
import os
from typing import Any

from core.errors.base import BaseError
from core.errors.codes import ErrorCode
from credentials.model import CREDENTIALS_PATH


def _path() -> str:
    """Return the expanded path to the credentials file."""
    return os.path.expanduser(CREDENTIALS_PATH)


def _read(path: str) -> dict[str, Any]:
    """Read the full credentials file.

    Raises ``BaseError`` if the file does not exist, is corrupt, or cannot be read.
    """
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise BaseError(ErrorCode.JSON, "Credentials file does not exist.")
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
    """Write the full credentials file with owner-only permissions.

    Raises ``BaseError`` if the write fails.
    """
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
    """Save or overwrite one connection. Other connections are unchanged.

    Raises ``BaseError`` if the credentials file does not exist or the write fails.
    """
    data = _read(_path())
    data[connection_name] = creds
    _write(_path(), data)


def load(connection_name: str) -> dict[str, Any]:
    """Load the stored fields for one connection.

    Raises ``BaseError`` with ``NOT_FOUND`` if the connection does not exist.
    """
    data = _read(_path()).get(connection_name, None)
    if data is None:
        raise BaseError(
            ErrorCode.NOT_FOUND,
            f"No connection data found for connection_name: {connection_name}",
        )
    return data


def delete(connection_name: str) -> None:
    """Remove one connection from the file.

    Does nothing if the connection is not in the file.
    Raises ``BaseError`` if the credentials file does not exist or the write fails.
    """
    data = _read(_path())
    if connection_name not in data:
        return
    del data[connection_name]
    _write(_path(), data)


def list() -> list[str]:
    """Return all connection names in the credentials file.

    Raises ``BaseError`` if the file does not exist or cannot be read.
    """
    return list(_read(_path()).keys())
