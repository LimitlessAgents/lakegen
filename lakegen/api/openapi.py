"""Dump the FastAPI OpenAPI document."""

from __future__ import annotations

from typing import Any


def openapi_document() -> dict[str, Any]:
    from lakegen.api.app import create_app

    return create_app().openapi()
