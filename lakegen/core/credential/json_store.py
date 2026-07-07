"""Read and write connection credentials in a JSON file.

Credentials are nested by kind and name in ``~/.lakegen/credentials.json``::

    {"catalog": {"prod": {...}}, "database": {"prod": {...}}}

The file must already exist before writes (created at app startup).

Writes are atomic (temp file + ``os.replace``) and serialized across processes
with a file lock, so two concurrent sessions cannot corrupt or lose each other's
data.

Raises ``BaseError`` with code ``JSON`` or ``NOT_FOUND`` on failure.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from filelock import FileLock, Timeout

from .model import CREDENTIALS_PATH
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode


def _path() -> str:
    """Return the expanded path to the credentials file."""
    return os.path.expanduser(CREDENTIALS_PATH)


def _lock(path: str) -> FileLock:
    """Return a cross-process file lock for the credentials file."""
    return FileLock(path + ".lock", timeout=10)


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
        ) from e
    except OSError as e:
        raise BaseError(
            ErrorCode.JSON,
            "Failed to read credentials file.",
        ) from e


def _write(path: str, data: dict[str, Any]) -> None:
    """Write the credentials file atomically with owner-only permissions.

    Writes to a temp file in the same directory, then replaces the target with
    ``os.replace``. On POSIX this replacement is atomic, so readers always see
    a complete file — never a truncated one from an in-progress write or crash.

    Raises ``BaseError`` if the write fails.
    """
    parent = Path(path).parent
    try:
        with tempfile.NamedTemporaryFile(
            "w", dir=parent, delete=False, suffix=".tmp"
        ) as f:
            json.dump(data, f, indent=2)
            tmp_path = f.name
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, path)
    except Exception as e:
        # Best-effort cleanup of the temp file before re-raising.
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise BaseError(
            ErrorCode.JSON,
            "Failed to write credentials file.",
        ) from e


def store(kind: str, name: str, creds: dict[str, Any]) -> None:
    """Save or overwrite one connection. Other connections are unchanged.

    Acquires an exclusive file lock before reading so that two concurrent
    processes cannot interleave their read-modify-write cycles and lose data.

    Raises ``BaseError`` if the lock times out, the file does not exist, or the
    write fails.
    """
    path = _path()
    try:
        with _lock(path):
            data = _read(path)
            if kind not in data:
                data[kind] = {}
            data[kind][name] = creds
            _write(path, data)
    except BaseError:
        raise
    except Timeout:
        raise BaseError(
            ErrorCode.UNAVAILABLE,
            "Could not acquire credentials file lock (another process is writing).",
        )


def load(kind: str, name: str) -> dict[str, Any]:
    """Load the stored fields for one connection.

    Reads without acquiring the write lock: atomic writes guarantee readers
    always see a complete file.

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

    Acquires an exclusive file lock before reading so the read-modify-write is
    atomic across processes.

    Raises ``BaseError`` if the lock times out, the file does not exist, or the
    write fails.
    """
    path = _path()
    try:
        with _lock(path):
            data = _read(path)
            kind_data = data.get(kind, {})
            if name not in kind_data:
                return
            del kind_data[name]
            if kind_data:
                data[kind] = kind_data
            elif kind in data:
                del data[kind]
            _write(path, data)
    except BaseError:
        raise
    except Timeout:
        raise BaseError(
            ErrorCode.UNAVAILABLE,
            "Could not acquire credentials file lock (another process is writing).",
        )


def list_connections(kind: str | None = None) -> dict[str, list[str]] | list[str]:
    """Return connection names, grouped by kind or for one kind.

    Raises ``BaseError`` if the credentials file cannot be read.
    """
    data = _read(_path())
    if kind is not None:
        return [*data.get(kind, {}).keys()]
    return {k: [*v.keys()] for k, v in data.items() if isinstance(v, dict)}
