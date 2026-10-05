import os

import pytest

from lakegen.session.session import Session
from lakegen.session.manager import SessionManager


def open_session(mgr: SessionManager, *args, **kwargs) -> Session:
    """Create a session and return the cached instance via get()."""
    return mgr.get(mgr.create(*args, **kwargs))


def pytest_configure(config: pytest.Config) -> None:
    """Block .env from enabling Postgres before test modules import the app."""
    os.environ["LAKEGEN_DATABASE_URL"] = ""


@pytest.fixture(autouse=True)
def _no_real_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep unit tests from opening Postgres unless a test opts into it."""
    monkeypatch.setenv("LAKEGEN_DATABASE_URL", "")
