"""Dump the FastAPI OpenAPI document."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI


def strip_fastapi_validation_errors(schema: dict[str, Any]) -> dict[str, Any]:
    """Remove FastAPI's default 422 validation responses from the spec."""
    components = schema.get("components", {})
    schemas = components.get("schemas", {})
    schemas.pop("HTTPValidationError", None)
    schemas.pop("ValidationError", None)

    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            responses = operation.get("responses")
            if not isinstance(responses, dict):
                continue
            response_422 = responses.get("422")
            if response_422 is None:
                continue
            json_schema = (
                response_422.get("content", {})
                .get("application/json", {})
                .get("schema", {})
            )
            if json_schema.get("$ref") == "#/components/schemas/HTTPValidationError":
                del responses["422"]

    return schema


def install_openapi(app: FastAPI) -> None:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        from fastapi.openapi.utils import get_openapi

        schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            description=app.description,
            routes=app.routes,
        )
        app.openapi_schema = strip_fastapi_validation_errors(schema)
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]


def openapi_document() -> dict[str, Any]:
    from lakegen.api.app import create_app

    return create_app().openapi()
