from typing import Any

from error.code import ErrorCode


class BaseError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        is_retryable: bool = False,
        is_user_fixable: bool = True,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.is_retryable = is_retryable
        self.is_user_fixable = is_user_fixable
        self.details = details or {}
        if cause is not None:
            self.__cause__ = cause
        super().__init__(message)

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "details": self.details or None,
            "cause": str(self.__cause__) if self.__cause__ else None,
            "is_retryable": self.is_retryable,
            "is_user_fixable": self.is_user_fixable,
        }
