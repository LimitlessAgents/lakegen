"""Auto-discover and register tool modules.

Any module whose name ends in ``_tool`` found anywhere inside the
``lakegen.tool`` package tree is imported automatically when
``discover_tools()`` is called. Each such module calls
``registry.register()`` at import time as a side effect, so no manual
import list needs to be maintained.

To add a new tool, create a file ending in ``_tool.py`` anywhere under
``lakegen/tool/`` — it will be picked up on the next startup with no
other changes required.
"""

import importlib
import pkgutil
import lakegen.tool as _root_pkg


def discover_tools() -> None:
    """Recursively import every ``*_tool`` module under ``lakegen.tool``.

    Walks the full package tree (``lakegen.tool`` itself and all
    sub-packages at any depth). Import failures are not silenced — a
    misconfigured tool file raises at startup rather than silently
    disappearing from the registry.
    """
    for pkg_info in pkgutil.walk_packages(
        path=_root_pkg.__path__,
        prefix=_root_pkg.__name__ + ".",
        onerror=_on_error,
    ):
        if pkg_info.name.rsplit(".", 1)[-1].endswith("_tool"):
            importlib.import_module(pkg_info.name)


def _on_error(name: str) -> None:
    """Re-raise import errors so broken tool packages fail loudly."""
    raise ImportError(f"Failed to scan package {name!r} during tool discovery.")
