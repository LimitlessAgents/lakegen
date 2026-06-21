"""Read and write secret credential fields in the OS keyring.

Uses the system vault (macOS Keychain, Windows Credential Manager, etc.) via the
``keyring`` package. Each secret is stored under ``<connection_name>/<field>``.

Raises ``BaseError`` with code ``KEYRING`` when the backend is missing or an
operation fails.
"""

from collections.abc import Iterable
from typing import Any

from .model import SERVICE_NAME
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode

# Cached keyring module so we only attempt the optional import once.
_backend: Any = None


def _get_backend() -> Any:
    """Return the keyring module, loading it on first use.

    Raises ``BaseError`` if the keyring package is not installed.
    """
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
    """Return the keyring key for one field of a connection."""
    return f"{connection_name}/{field}"


def set_secret(connection_name: str, field: str, value: Any) -> None:
    """Write one secret field to the keyring.

    Raises ``BaseError`` on failure.
    """
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
    """Read one secret field from the keyring.

    Returns ``None`` if the field is not stored.
    Raises ``BaseError`` if the keyring is unavailable or the read fails.
    """
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
    """Remove one secret field from the keyring.

    Raises ``BaseError`` on failure.
    """
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
    """Write all secret fields for a connection.

    If any field fails, previously written fields are rolled back, then the
    error is raised. The keyring never keeps a partial set of secrets.

    Raises ``BaseError`` on failure.
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
    """Remove the given secret fields for a connection.

    Ignores fields that fail to delete. Used for rollback and cleanup.
    """
    for field in fields:
        try:
            delete_secret(connection_name, field)
        except BaseError:
            pass
