"""Read and write connection credentials in a JSON file.

Credentials are nested by kind and name in ``~/.lakegen/credentials.json``::

    {"catalogs": {"prod": {...}}, "databases": {"prod": {...}}}

The file must already exist before writes (created at app startup).

Raises ``BaseError`` with code ``JSON`` or ``NOT_FOUND`` on failure.
"""

import json
import os
from typing import Any

from .model import CREDENTIALS_PATH
from error.base import BaseError
from error.code import ErrorCode


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


def store(kind: str, name: str, creds: dict[str, Any]) -> None:
    """Save or overwrite one connection. Other connections are unchanged.

    Raises ``BaseError`` if the credentials file does not exist or the write fails.
    """
    data = _read(_path())
    if kind not in data:
        data[kind] = {}
    data[kind][name] = creds
    _write(_path(), data)


def load(kind: str, name: str) -> dict[str, Any]:
    """Load the stored fields for one connection.

    Raises ``BaseError`` with ``NOT_FOUND`` if the connection does not exist.
    """
    creds = _read(_path()).get(kind, {}).get(name)
    if creds is None:
        raise BaseError(
            ErrorCode.NOT_FOUND,
            f"No connection data found for {kind}/{name}.",
        )
    return creds


def delete(kind: str, name: str) -> None:
    """Remove one connection from the file.

    Does nothing if the connection is not in the file.
    Raises ``BaseError`` if the credentials file does not exist or the write fails.
    """
    data = _read(_path())
    kind_data = data.get(kind, {})
    if name not in kind_data:
        return
    del kind_data[name]
    if kind_data:
        data[kind] = kind_data
    elif kind in data:
        del data[kind]
    _write(_path(), data)


def list(kind: str | None = None) -> dict[str, list[str]] | list[str]:
    """Return connection names, grouped by kind or for one kind.

    Raises ``BaseError`` if the credentials file cannot be read.
    """
    data = _read(_path())
    if kind is not None:
        return list(data.get(kind, {}).keys())
    return {k: list(v.keys()) for k, v in data.items() if isinstance(v, dict)}
