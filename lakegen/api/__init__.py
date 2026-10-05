"""HTTP BFF for LakeGen (FastAPI)."""

__all__ = ["app", "create_app"]


def __getattr__(name: str):
    if name in __all__:
        import lakegen.api.app as app_module

        return getattr(app_module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
