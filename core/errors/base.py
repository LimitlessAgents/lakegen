from core.errors.codes import ErrorCode

class BaseError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: Optional[dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        if cause is not None:
            self.__cause__ = cause
        super().__init__(message)

    def __str__(self) - > str:
        return f"{self.code.value}: {self.message}"