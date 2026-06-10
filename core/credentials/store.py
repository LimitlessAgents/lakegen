"""Public API for saving and loading lakehouse connection credentials.

Secrets (passwords, tokens, keys) are stored in the OS keyring when possible.
Everything else is stored in a JSON file. If the keyring is unavailable, secrets
are written to the JSON file instead.

All functions raise ``BaseError`` on failure. Tools should catch those errors
and return them to the agent.
"""

from typing import Any

from core.errors.base import BaseError
from core.errors.codes import ErrorCode
from credentials import json_store, keyring_store
from credentials.model import KEYRING_PLACEHOLDER, SENSITIVE_FIELDS


def store_credentials(connection_name: str, creds: dict[str, Any]) -> None:
    """Save credentials for a connection.

    Tries the keyring first for secret fields and writes placeholders to JSON.
    If the keyring is unavailable, stores everything in JSON instead.
    Rolls back the keyring if the JSON write fails afterward.

    Raises:
        ``BaseError`` if both backends fail, or if JSON fails after a
        successful keyring write (keyring is rolled back first).
    """
    secrets = {k: v for k, v in creds.items() if k in SENSITIVE_FIELDS}

    try:
        keyring_store.store(connection_name, secrets)
    except BaseError as ke:
        try:
            json_store.store(connection_name, creds)
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
        json_store.store(connection_name, redacted)
    except BaseError as e:
        keyring_store.delete(connection_name, secrets.keys())
        raise BaseError(
            ErrorCode.JSON,
            "Secrets written to keyring but JSON write failed; rolled back keyring.",
            details={"cause": e.message},
            cause=e,
        ) from e


def get_credentials(connection_name: str) -> dict[str, Any]:
    """Load credentials for a connection.

    Reads from JSON and fills in any secret fields from the keyring.

    Raises:
        ``BaseError`` if the connection does not exist or a backend read fails.
    """
    creds = json_store.load(connection_name)
    for field, value in creds.items():
        if value == KEYRING_PLACEHOLDER:
            creds[field] = keyring_store.get_secret(connection_name, field)
    return creds


def delete_credentials(connection_name: str) -> None:
    """Delete a connection and all of its credentials.

    Removes secrets from the keyring and the entry from the JSON file.

    Raises:
        ``BaseError`` if the connection does not exist or a backend delete fails.
    """
    stored = json_store.load(connection_name)
    secret_fields = [f for f, v in stored.items() if v == KEYRING_PLACEHOLDER]
    keyring_store.delete(connection_name, secret_fields)
    json_store.delete(connection_name)


def list_connections() -> list[str]:
    """Return the names of all saved connections.

    Raises:
        ``BaseError`` if the credentials file cannot be read.
    """
    return json_store.list()
