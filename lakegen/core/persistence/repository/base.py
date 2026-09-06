from abc import ABC, abstractmethod
from collections.abc import Mapping

from lakegen.core.persistence import PostgresPersistence, persistence


class Repository(ABC):
    """Common contract for persistence repositories."""

    def __init__(
        self,
        database: PostgresPersistence = persistence,
    ) -> None:
        self._database = database

    @abstractmethod
    def create(self, data: Mapping[str, object]) -> None:
        """Create one record."""

    @abstractmethod
    def get(self, identifier: str) -> dict[str, object]:
        """Return one record."""

    @abstractmethod
    def exists(self, identifier: str) -> bool:
        """Return whether one record exists."""

    @abstractmethod
    def delete(self, identifier: str) -> None:
        """Delete one record."""

    @staticmethod
    def _required_string(
        payload: Mapping[str, object],
        field: str,
    ) -> str:
        value = payload.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field} must be a non-empty string.")
        return value
