"""Constants and types shared by the credential storage backends."""

from dataclasses import dataclass
from typing import Any

# Service name used for all keyring entries.
SERVICE_NAME = "lakegen"

# Path to the JSON credentials file (~ is expanded at runtime).
CREDENTIALS_PATH = "~/.lakegen/credentials.json"

# Placeholder written in JSON when the real secret lives in the keyring.
KEYRING_PLACEHOLDER = "<stored_in_keyring>"

# Credential field names stored in the keyring instead of plaintext JSON.
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
    """Legacy result type for credential write operations. Prefer raising ``BaseError``."""

    connection_name: str | None
    success: bool
    error: str | None = None

    output: Any

    def __bool__(self) -> bool:
        return self.success
