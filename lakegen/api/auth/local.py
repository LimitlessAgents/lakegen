from __future__ import annotations

from starlette.requests import Request

from lakegen.api.auth.authenticator import Principal

_DEFAULT_USER_ID = "local"
_DEFAULT_DISPLAY = "Local User"
_HEADER = "x-user"


class LocalAuth:
    """Single-user auth for local/dev. Optional ``X-User`` overrides the id."""

    def __init__(
        self,
        *,
        default_user_id: str = _DEFAULT_USER_ID,
        default_display_name: str = _DEFAULT_DISPLAY,
    ) -> None:
        self._default_user_id = default_user_id
        self._default_display_name = default_display_name

    def resolve(self, request: Request) -> Principal:
        user_id = request.headers.get(_HEADER) or self._default_user_id
        display = (
            self._default_display_name
            if user_id == self._default_user_id
            else user_id
        )
        return Principal(id=user_id, display_name=display)
