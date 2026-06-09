"""Data models and configuration for credential storage.

These values are shared by the keyring and JSON backends as well as the
high-level orchestration in ``credentials.store``.
"""

from dataclasses import dataclass

# Namespace used for every entry written to the OS keyring.
SERVICE_NAME = "lakegen"

# Location of the JSON file that holds non-secret fields and placeholders.
CREDENTIALS_PATH = "~/.lakegen/credentials.json"

# Written into the JSON file in place of a secret whose real value lives in
# the keyring. ``get_credentials`` uses it to know which fields to fetch back.
KEYRING_PLACEHOLDER = "<stored_in_keyring>"

# Fields treated as secrets: stored in the keyring instead of plaintext JSON.
SENSITIVE_FIELDS = frozenset(
    {
        "password",
        "access_key",
        "secret_key",
        "glue_access_key",
        "glue_secret_key",
        "credential",
        "token",
    }
)


@dataclass
class StoreResult:
    """Outcome of a write operation.

    Returned instead of raising so callers can inspect
    ``success`` and read ``error`` to decide how to recover.
    """

    connection_name: str | None
    success: bool
    error: str | None = None

    output: Any

    def __bool__(self) -> bool:
        return self.success
