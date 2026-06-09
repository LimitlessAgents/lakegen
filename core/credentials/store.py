"""High-level credential storage combining the keyring and JSON backends.

Storage strategy:
  - Secret fields (``SENSITIVE_FIELDS``) go into the OS keyring, and the JSON
    file keeps a placeholder in their place.
  - Non-secret fields are stored as-is in the JSON file.
  - If no keyring is available, the full credentials fall back to plaintext
    JSON so the connection still works.
"""

from typing import Any

from core.errors.base import BaseError
from core.errors.codes import ErrorCode
from credentials import json_store, keyring_store
from credentials.model import KEYRING_PLACEHOLDER, SENSITIVE_FIELDS


def store_credentials(connection_name: str, creds: Dict[str, Any]) -> None:
    """Persist a connection's credentials across the keyring and JSON backends.

    Secrets are written to the keyring and the JSON copy keeps placeholders. If
    the keyring write succeeds but the JSON write fails, the keyring changes are
    rolled back so the two backends never disagree.
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
    """Return a connection's full credentials, resolving keyring-backed secrets."""
    creds = json_store.load(connection_name)
    for field, value in creds.items():
        if value == KEYRING_PLACEHOLDER:
            creds[field] = keyring_store.get_secret(connection_name, field)
    return creds


def delete_credentials(connection_name: str) -> None:
    """Remove a connection from both backends."""
    stored = json_store.load(connection_name)
    secret_fields = [f for f, v in stored.items() if v == KEYRING_PLACEHOLDER]
    keyring_store.delete(connection_name, secret_fields)
    json_store.delete(connection_name)


def list_connections() -> list[str]:
    """List all available connection names from the JSON backend."""
    return json_store.list()
