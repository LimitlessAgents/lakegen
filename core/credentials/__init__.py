"""Credential storage for lakegen connections.

    from credentials import (
        store_credentials,
        get_credentials,
        delete_credentials,
        list_connections,
    )

All functions raise ``BaseError`` on failure.
"""

from credentials.store import (
    delete_credentials,
    get_credentials,
    list_connections,
    store_credentials,
)

__all__ = [
    "store_credentials",
    "get_credentials",
    "delete_credentials",
    "list_connections",
]
