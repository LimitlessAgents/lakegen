from typing import Any

from lakegen.core.error.code import ErrorCode


class BaseError(Exception):
    """Application error carrying structured, agent-readable context.

    Beyond a code and message, the flags describe how a caller (often the agent)
    should react: ``is_retryable`` hints the same call may succeed if retried,
    and ``is_user_fixable`` hints the input or config can be corrected. Left
    unset, both flags are inherited from the cause, so a wrapper reflects the
    retryability of the error it wraps (e.g. wrapping a retryable timeout stays
    retryable) unless it explicitly overrides.

    Chaining convention: when raising, attach the underlying error with
    ``raise BaseError(...) from err``. That sets ``__cause__``, which ``to_dict``
    serializes recursively so the full lineage down to the root exception is
    preserved. Use the ``cause`` argument only when *constructing* an error to
    return rather than raise (e.g. at the tool boundary). Do not use both. In
    either case, ``details`` is reserved for context about *this* level (e.g. the
    offending toolset or type), never for the child error itself.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        is_retryable: bool | None = None,
        is_user_fixable: bool | None = None,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        self.code = code
        self.message = message
        # None means "inherit from the cause"; see the properties below.
        self._is_retryable = is_retryable
        self._is_user_fixable = is_user_fixable
        self.details = details or {}
        if cause is not None:
            self.__cause__ = cause
        super().__init__(message)

    @property
    def is_retryable(self) -> bool:
        """Explicit value if set, else inherit from the cause, else False."""
        if self._is_retryable is not None:
            return self._is_retryable
        if isinstance(self.__cause__, BaseError):
            return self.__cause__.is_retryable
        return False

    @property
    def is_user_fixable(self) -> bool:
        """Explicit value if set, else inherit from the cause, else True."""
        if self._is_user_fixable is not None:
            return self._is_user_fixable
        if isinstance(self.__cause__, BaseError):
            return self.__cause__.is_user_fixable
        return True

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        cause = self.__cause__
        if isinstance(cause, BaseError):
            cause_repr = cause.to_dict()          # full structured lineage
        elif cause is not None:
            cause_repr = {"type": type(cause).__name__, "message": str(cause)}
        else:
            cause_repr = None
        return {
            "code": self.code.value,
            "message": self.message,
            "details": self.details or None,
            "cause": cause_repr,
            "is_retryable": self.is_retryable,
            "is_user_fixable": self.is_user_fixable,
        }
