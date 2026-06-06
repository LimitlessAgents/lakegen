"""Keyring-backed storage for sensitive credential fields.

Secrets are kept in the OS-native vault (macOS Keychain, Windows Credential
Manager, Linux Secret Service) via the optional ``keyring`` package. When no
backend is installed every function degrades gracefully: reads return ``None``
and writes/deletes report failure instead of raising.

Keyring is a flat key/value store, so each field is stored under the key
``"<connection_name>/<field>"``.
"""

from typing import Any, Dict, List

from credentials.model import SERVICE_NAME, StoreResult

# Cached keyring module so we only attempt the optional import once.
_backend: Any = None


def _get_backend() -> Any:
    """Return the imported ``keyring`` module, or ``None`` if unavailable."""
    global _backend
    if _backend:
        return _backend
    try:
        import keyring
    except ImportError:
        return None
    _backend = keyring
    return _backend


def _entry_key(connection_name: str, field: str) -> str:
    """Build the flat keyring key for one field of a connection."""
    return f"{connection_name}/{field}"


def set_secret(connection_name: str, field: str, value: Any) -> bool:
    """Store a single secret. Returns ``False`` if no keyring is available."""
    backend = _get_backend()
    if not backend:
        return False
    backend.set_password(SERVICE_NAME, _entry_key(connection_name, field), value)
    return True


def get_secret(connection_name: str, field: str) -> str | None:
    """Read a single secret, or ``None`` if missing or no keyring is available."""
    backend = _get_backend()
    if not backend:
        return None
    return backend.get_password(SERVICE_NAME, _entry_key(connection_name, field))


def delete_secret(connection_name: str, field: str) -> bool:
    """Remove a single secret. Returns ``False`` if no keyring is available."""
    backend = _get_backend()
    if not backend:
        return False
    backend.delete_password(SERVICE_NAME, _entry_key(connection_name, field))
    return True


def store(connection_name: str, secrets: Dict[str, Any]) -> StoreResult:
    """Store all secret fields atomically.

    If any field fails to write, the ones already written are rolled back so
    the keyring is never left holding a partial set of credentials.
    """
    backend = _get_backend()
    if not backend:
        return StoreResult(False, "keyring backend unavailable")

    written: List[str] = []
    for field, value in secrets.items():
        if not set_secret(connection_name, field, value):
            for done in written:
                delete_secret(connection_name, done)
            return StoreResult(
                False,
                f"failed to store field '{field}' in keyring; "
                f"rolled back {len(written)} field(s)",
            )
        written.append(field)
    return StoreResult(True)


def delete(connection_name: str, fields: Any) -> bool:
    """Best-effort removal of the given fields for a connection."""
    backend = _get_backend()
    if not backend:
        return False
    for field in fields:
        delete_secret(connection_name, field)
    return True
