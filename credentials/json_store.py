"""JSON-file-backed storage for connection credentials.

The file holds one entry per connection, keyed by connection name, with each
value being a dict of ``field -> value``. Secret fields are replaced with
``KEYRING_PLACEHOLDER`` when their real values live in the keyring.

The file is expected to already exist (created during application startup);
writes to a missing file are treated as a failure rather than created here.
"""

import json
import os
from typing import Any, Dict

from credentials.model import CREDENTIALS_PATH


def _path() -> str:
    """Absolute path to the credentials file, with ``~`` expanded."""
    return os.path.expanduser(CREDENTIALS_PATH)


def _read(path: str) -> Dict[str, Any]:
    """Load the whole store. Returns ``{}`` if the file is missing or corrupt."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # TODO: surface corrupt-file recovery instead of silently resetting.
        return {}


def _write(path: str, data: Dict[str, Any]) -> bool:
    """Write the whole store and restrict the file to owner-only access."""
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        os.chmod(path, 0o600)
        return True
    except (OSError, TypeError):
        return False


def store(connection_name: str, creds: Dict[str, Any]) -> bool:
    """Save (or overwrite) one connection's credentials. Other entries are kept."""
    path = _path()
    if not os.path.exists(path):
        return False
    data = _read(path)
    data[connection_name] = creds
    return _write(path, data)


def load(connection_name: str) -> Dict[str, Any]:
    """Return one connection's stored fields, or ``{}`` if it does not exist."""
    return _read(_path()).get(connection_name, {})


def delete(connection_name: str) -> bool:
    """Remove one connection. Returns ``True`` if it is absent or removed."""
    path = _path()
    if not os.path.exists(path):
        return False
    data = _read(path)
    if connection_name not in data:
        return True
    del data[connection_name]
    return _write(path, data)
