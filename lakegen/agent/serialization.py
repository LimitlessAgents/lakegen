import json
from dataclasses import asdict
from typing import Any

from lakegen.agent.model import AgentLoopResult


def serialize_agent_loop_result(result: AgentLoopResult) -> dict[str, Any]:
    """Convert an agent result into JSON-compatible data."""
    return json.loads(json.dumps(asdict(result)))
