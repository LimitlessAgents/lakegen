"""Convert PyIceberg / PyArrow inspect results into JSON-native values."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any


def arrow_table_to_rows(table: Any) -> list[dict[str, Any]]:
    """Convert a ``pyarrow.Table`` to a list of JSON-serializable dicts.

    Handles timestamps, dates, nested structs, maps (as key/value pairs from
    Arrow), and bytes. Callers must pass a real Arrow table (or a duck-typed
    object with ``to_pylist``).
    """
    return [_json_safe(row) for row in table.to_pylist()]


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        # Arrow maps often become a list of (key, value) pairs via to_pylist.
        if value and all(
            isinstance(item, (list, tuple)) and len(item) == 2 for item in value
        ):
            return {
                str(_json_safe(key)): _json_safe(item)
                for key, item in value
            }
        return [_json_safe(item) for item in value]
    return str(value)
