"""Map domain ``BaseError`` to HTTP responses."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from lakegen.api.schema import ErrorBody
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode

_STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.INVALID_ARGUMENT: 400,
    ErrorCode.INVALID_TYPE: 400,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.ALREADY_EXISTS: 409,
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.PERMISSION_DENIED: 403,
    ErrorCode.CONNECTION_FAILED: 502,
    ErrorCode.CONNECTION_TIMEOUT: 504,
    ErrorCode.UNAVAILABLE: 503,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.MODEL_NOT_FOUND: 404,
    ErrorCode.INFERENCE_FAILED: 502,
}


def http_status_for(code: ErrorCode) -> int:
    return _STATUS_BY_CODE.get(code, 500)


def error_body_for(error: BaseError) -> ErrorBody:
    """Translate an internal agent error into a safe client response."""
    status_code = http_status_for(error.code)
    if status_code >= 500:
        return ErrorBody(message="The service is temporarily unavailable.")
    return ErrorBody(message=error.message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BaseError)
    async def base_error_handler(_request: Request, exc: BaseError) -> JSONResponse:
        return JSONResponse(
            status_code=http_status_for(exc.code),
            content=error_body_for(exc).model_dump(mode="json"),
        )
