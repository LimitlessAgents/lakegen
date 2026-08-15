"""OpenAPI response declarations for service errors."""

from __future__ import annotations

from typing import Any

from lakegen.api.errors import SERVICE_ERROR_STATUS_CODES
from lakegen.api.schema import ErrorBody

_ERROR = {"model": ErrorBody, "description": "Service error."}

# Generated from the statuses emitted by the API exception handlers.
SERVICE_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status_code: _ERROR for status_code in SERVICE_ERROR_STATUS_CODES
}
