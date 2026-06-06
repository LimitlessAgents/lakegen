"""High-level credential storage combining the keyring and JSON backends.

Storage strategy:
  - Secret fields (``SENSITIVE_FIELDS``) go into the OS keyring, and the JSON
    file keeps a placeholder in their place.
  - Non-secret fields are stored as-is in the JSON file.
  - If no keyring is available, the full credentials fall back to plaintext
    JSON so the connection still works.

All write functions return a ``StoreResult`` so callers can react to failures
rather than catch exceptions.
"""

from typing import Any, Dict

from credentials import json_store, keyring_store
from credentials.model import KEYRING_PLACEHOLDER, SENSITIVE_FIELDS, StoreResult


def store_credentials(connection_name: str, creds: Dict[str, Any]) -> StoreResult:
    """Persist a connection's credentials across the keyring and JSON backends.

    Secrets are written to the keyring and the JSON copy keeps placeholders. If
    the keyring write succeeds but the JSON write fails, the keyring changes are
    rolled back so the two backends never disagree.
    """
    secrets = {k: v for k, v in creds.items() if k in SENSITIVE_FIELDS}

    keyring_result = keyring_store.store(connection_name, secrets)
    if not keyring_result:
        # No keyring (or it failed): fall back to storing everything in JSON.
        if json_store.store(connection_name, creds):
            return StoreResult(True)
        return StoreResult(
            False,
            f"keyring unavailable ({keyring_result.error}) and JSON write failed",
        )

    redacted = {
        k: (KEYRING_PLACEHOLDER if k in SENSITIVE_FIELDS else v)
        for k, v in creds.items()
    }
    if not json_store.store(connection_name, redacted):
        keyring_store.delete(connection_name, secrets.keys())
        return StoreResult(
            False,
            "secrets written to keyring but JSON write failed; rolled back keyring",
        )
    return StoreResult(True)


def get_credentials(connection_name: str) -> Dict[str, Any]:
    """Return a connection's full credentials, resolving keyring-backed secrets.

    Reads the JSON entry and replaces every ``KEYRING_PLACEHOLDER`` with the real
    value fetched from the keyring. Returns ``{}`` if the connection is unknown.
    """
    creds = json_store.load(connection_name)
    for field, value in creds.items():
        if value == KEYRING_PLACEHOLDER:
            creds[field] = keyring_store.get_secret(connection_name, field)
    return creds


def delete_credentials(connection_name: str) -> StoreResult:
    """Remove a connection from both backends.

    Secrets currently in the keyring (identified by their JSON placeholders) are
    deleted first, then the JSON entry is removed.
    """
    stored = json_store.load(connection_name)
    secret_fields = [f for f, v in stored.items() if v == KEYRING_PLACEHOLDER]
    keyring_store.delete(connection_name, secret_fields)

    if not json_store.delete(connection_name):
        return StoreResult(False, "failed to remove connection from JSON store")
    return StoreResult(True)
