"""Map domain ``BaseError`` to HTTP responses."""

from __future__ import annotations

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from lakegen.api.schema import ErrorBody
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode

_STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.INVALID_ARGUMENT: 400,
    ErrorCode.INVALID_TYPE: 400,
    ErrorCode.METHOD_NOT_ALLOWED: 405,
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
    ErrorCode.KEYRING: 500,
    ErrorCode.JSON: 500,
    ErrorCode.INTERNAL: 500,
}

_HTTP_CODE_TO_ERROR: dict[int, ErrorCode] = {}
for _code, _status in _STATUS_BY_CODE.items():
    _HTTP_CODE_TO_ERROR.setdefault(_status, _code)

SERVICE_ERROR_STATUS_CODES = frozenset(_STATUS_BY_CODE.values())


def http_status_for(code: ErrorCode) -> int:
    return _STATUS_BY_CODE.get(code, _STATUS_BY_CODE[ErrorCode.INTERNAL])


def code_for_http_status(status_code: int) -> ErrorCode:
    return _HTTP_CODE_TO_ERROR.get(status_code, ErrorCode.INTERNAL)


def error_body_for(error: BaseError) -> ErrorBody:
    """Translate an internal agent error into a safe client response."""
    return error_body_for_code(error.code, error.message)


def error_body_for_code(code: ErrorCode, message: str) -> ErrorBody:
    if http_status_for(code) >= 500:
        return ErrorBody(
            code=code,
            message="The service is temporarily unavailable.",
        )
    return ErrorBody(code=code, message=message)


def error_response(
    code: ErrorCode,
    message: str,
    *,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=http_status_for(code),
        content=error_body_for_code(code, message).model_dump(mode="json"),
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BaseError)
    async def base_error_handler(_request: Request, exc: BaseError) -> JSONResponse:
        return error_response(exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return error_response(
            ErrorCode.INVALID_ARGUMENT,
            "Request validation failed.",
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(
        _request: Request, exc: HTTPException
    ) -> JSONResponse:
        code = code_for_http_status(exc.status_code)
        detail = exc.detail
        message = (
            detail if isinstance(detail, str) else HTTPStatus(exc.status_code).phrase
        )
        return error_response(code, message, headers=exc.headers)

    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        _request: Request, _exc: Exception
    ) -> JSONResponse:
        return error_response(
            ErrorCode.INTERNAL,
            "The service is temporarily unavailable.",
        )
