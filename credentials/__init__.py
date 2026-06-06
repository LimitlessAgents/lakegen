"""Credential storage for lakegen connections.

Secrets are kept in the OS keyring when available; the rest live in a JSON
file. Import the high-level API from here:

    from credentials import store_credentials, get_credentials, delete_credentials
"""

from credentials.model import StoreResult
from credentials.store import (
    delete_credentials,
    get_credentials,
    store_credentials,
)

__all__ = [
    "StoreResult",
    "store_credentials",
    "get_credentials",
    "delete_credentials",
]
