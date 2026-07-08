"""Helpers for recovering a corrupt credentials JSON file."""

import json
import os
from pathlib import Path
from typing import Any


def repair_json_file(path: str) -> dict[str, Any]:
    """Attempt to parse corrupt JSON from ``path`` using json-repair."""
    import json_repair

    repaired = json_repair.from_file(path)
    if isinstance(repaired, dict):
        return repaired
    raise ValueError(
        f"Repaired credentials file did not produce a dict (got {type(repaired).__name__})."
    )


def recreate_json_file(path: str) -> dict[str, Any]:
    print("Recreating json file")
    """Replace ``path`` with a fresh empty credentials object."""
    parent = Path(path).parent
    parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump({}, f)
    os.chmod(path, 0o600)
    return {}
