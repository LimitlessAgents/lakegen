"""Keyring-backed storage for sensitive credential fields.

Secrets are kept in the OS-native vault (macOS Keychain, Windows Credential
Manager, Linux Secret Service) via the optional ``keyring`` package. When no
backend is installed, write paths raise ``BaseError`` with code ``KEYRING`` so
callers can fall back; reads return ``None`` and deletes are no-ops.

Keyring is a flat key/value store, so each field is stored under the key
``"<connection_name>/<field>"``.
"""

from typing import Any
from collections.abc import Iterable

from core.errors.base import BaseError
from core.errors.codes import ErrorCode
from credentials.model import SERVICE_NAME

# Cached keyring module so we only attempt the optional import once.
_backend: Any = None


def _get_backend() -> Any:
    """Return the imported ``keyring`` module"""
    global _backend
    if _backend:
        return _backend
    try:
        import keyring
    except ImportError:
        raise BaseError(ErrorCode.KEYRING, "keyring backend unavailable")
    _backend = keyring
    return _backend


def _entry_key(connection_name: str, field: str) -> str:
    """Build the flat keyring key for one field of a connection."""
    return f"{connection_name}/{field}"


def set_secret(connection_name: str, field: str, value: Any) -> None:
    """Store a single secret. Raises ``BaseError`` on failure."""
    try:
        backend = _get_backend()
        backend.set_password(SERVICE_NAME, _entry_key(connection_name, field), value)
    except BaseError:
        raise
    except Exception as e:
        raise BaseError(
            ErrorCode.KEYRING,
            f"Failed to store field '{field}' in keyring for connection '{connection_name}'.",
            cause=e,
        )


def get_secret(connection_name: str, field: str) -> str | None:
    """Read a single secret"""
    try:
        backend = _get_backend()
        return backend.get_password(SERVICE_NAME, _entry_key(connection_name, field))
    except BaseError:
        raise
    except Exception as e:
        raise BaseError(
            ErrorCode.KEYRING,
            f"Failed to read field '{field}' from keyring for connection '{connection_name}'.",
            cause=e,
        )

def delete_secret(connection_name: str, field: str) -> None:
    """Remove a single secret. Raises ``BaseError`` on failure."""
    try:
        backend = _get_backend()
        backend.delete_password(SERVICE_NAME, _entry_key(connection_name, field))
    except BaseError:
        raise
    except Exception as e:
        raise BaseError(
            ErrorCode.KEYRING,
            f"Failed to delete field '{field}' from keyring for connection '{connection_name}'.",
            cause=e,
        )


def store(connection_name: str, secrets: dict[str, Any]) -> None:
    """Store all secret fields atomically.

    If any field fails to write, the ones already written are rolled back so
    the keyring is never left holding a partial set of credentials.
    """
    written: list[str] = []
    for field, value in secrets.items():
        try:
            set_secret(connection_name, field, value)
            written.append(field)
        except BaseError:
            delete(connection_name, written)
            raise
        

def delete(connection_name: str, fields: Iterable[str]) -> None:
    """Best-effort removal of the given fields for a connection."""
    for field in fields:
        try:
            delete_secret(connection_name, field)
        except BaseError:
            pass
