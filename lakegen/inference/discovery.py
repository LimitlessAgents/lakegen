"""Auto-discover and register inference providers.

Any module found inside ``lakegen.inference.providers`` is imported
automatically when ``discover_providers()`` is called. Each provider
module calls ``registry.register()`` at import time as a side effect, so
no manual import list needs to be maintained.

To add a new provider, create a module under ``lakegen/inference/providers/``
that calls ``registry.register(...)`` — it will be picked up on the next
startup with no other changes required.
"""

import importlib
import pkgutil
from pathlib import Path

import lakegen.inference as _inference_pkg

_PROVIDERS_DIR = "providers"


def discover_providers() -> None:
    """Import every module under ``lakegen.inference.providers``.

    Import failures are not silenced — a misconfigured provider module
    raises at startup rather than silently disappearing from the registry.
    """
    providers_path = Path(_inference_pkg.__path__[0]) / _PROVIDERS_DIR
    prefix = f"{_inference_pkg.__name__}.{_PROVIDERS_DIR}."

    for module_info in pkgutil.iter_modules(
        path=[str(providers_path)],
        prefix=prefix,
    ):
        if module_info.ispkg:
            continue
        importlib.import_module(module_info.name)
