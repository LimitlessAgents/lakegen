import os

import pytest


@pytest.fixture(autouse=True)
def _no_real_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep unit tests from opening Postgres unless a test opts into it."""
    monkeypatch.delenv("LAKEGEN_DATABASE_URL", raising=False)
