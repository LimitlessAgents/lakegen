"""Public API for saving and loading lakehouse connection credentials.

Secrets (passwords, tokens, keys) are stored in the OS keyring when possible.
Everything else is stored in a JSON file. If the keyring is unavailable, secrets
are written to the JSON file instead.

All functions raise ``BaseError`` on failure. Tools should catch those errors
and return them to the agent.
"""

from typing import Any

from . import json_store, keyring_store
from .model import KEYRING_PLACEHOLDER, SENSITIVE_FIELDS
from error.base import BaseError
from error.code import ErrorCode


def _keyring_id(kind: str, name: str) -> str:
    """Return the keyring namespace for a kind/name connection."""
    return f"{kind}/{name}"


def store_credentials(kind: str, name: str, creds: dict[str, Any]) -> None:
    """Save credentials for a connection.

    Tries the keyring first for secret fields and writes placeholders to JSON.
    If the keyring is unavailable, stores everything in JSON instead.
    Rolls back the keyring if the JSON write fails afterward.

    Raises:
        ``BaseError`` if both backends fail, or if JSON fails after a
        successful keyring write (keyring is rolled back first).
    """
    keyring_name = _keyring_id(kind, name)
    secrets = {k: v for k, v in creds.items() if k in SENSITIVE_FIELDS}

    try:
        keyring_store.store(keyring_name, secrets)
    except BaseError as ke:
        try:
            json_store.store(kind, name, creds)
        except BaseError as je:
            raise BaseError(
                ErrorCode.UNAVAILABLE,
                "Failed to store credentials.",
                details={"keyring": ke.message, "json": je.message},
                cause=je,
            ) from je
        return

    redacted = {
        k: (KEYRING_PLACEHOLDER if k in SENSITIVE_FIELDS else v)
        for k, v in creds.items()
    }
    try:
        json_store.store(kind, name, redacted)
    except BaseError as e:
        keyring_store.delete(keyring_name, secrets.keys())
        raise BaseError(
            ErrorCode.JSON,
            "Secrets written to keyring but JSON write failed; rolled back keyring.",
            details={"cause": e.message},
            cause=e,
        ) from e


def get_credentials(kind: str, name: str) -> dict[str, Any]:
    """Load credentials for a connection.

    Reads from JSON and fills in any secret fields from the keyring.

    Raises:
        ``BaseError`` if the connection does not exist or a backend read fails.
    """
    keyring_name = _keyring_id(kind, name)
    creds = json_store.load(kind, name)
    for field, value in creds.items():
        if value == KEYRING_PLACEHOLDER:
            creds[field] = keyring_store.get_secret(keyring_name, field)
    return creds


def delete_credentials(kind: str, name: str) -> None:
    """Delete a connection and all of its credentials.

    Removes secrets from the keyring and the entry from the JSON file.

    Raises:
        ``BaseError`` if the connection does not exist or a backend delete fails.
    """
    keyring_name = _keyring_id(kind, name)
    stored = json_store.load(kind, name)
    secret_fields = [f for f, v in stored.items() if v == KEYRING_PLACEHOLDER]
    keyring_store.delete(keyring_name, secret_fields)
    json_store.delete(kind, name)


def list_connections(kind: str | None = None) -> dict[str, list[str]] | list[str]:
    """Return saved connection names, grouped by kind or for one kind.

    Raises:
        ``BaseError`` if the credentials file cannot be read.
    """
    return json_store.list(kind)
