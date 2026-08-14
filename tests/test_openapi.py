"""OpenAPI snapshot must match the running app."""

from __future__ import annotations

import json
from pathlib import Path

from lakegen.api.openapi import openapi_document

_SNAPSHOT = Path(__file__).resolve().parents[1] / "openapi" / "v1.json"


def test_openapi_matches_snapshot() -> None:
    generated = openapi_document()
    committed = json.loads(_SNAPSHOT.read_text())
    assert generated == committed, (
        "OpenAPI drifted from openapi/v1.json. Re-export with:\n"
        "  uv run python -c \"from pathlib import Path; import json; "
        "from lakegen.api.openapi import openapi_document; "
        "Path('openapi/v1.json').write_text(json.dumps(openapi_document(), indent=2) + chr(10))\""
    )
