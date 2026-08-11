"""HTTP BFF for LakeGen (FastAPI)."""

from lakegen.api.app import app, create_app

__all__ = ["app", "create_app"]
