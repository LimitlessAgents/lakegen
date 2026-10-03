import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from typing import Any

from lakegen.agent.model import AgentLoopResult, Conversation
from lakegen.inference import Message, Role
from lakegen.tool.model import ToolCall


def serialize_agent_loop_result(result: AgentLoopResult) -> dict[str, Any]:
    """Convert an agent result into JSON-compatible data."""
    return json.loads(json.dumps(asdict(result)))


def _message_from_mapping(data: Mapping[str, object]) -> Message | None:
    role_value = data.get("role")
    if not isinstance(role_value, str):
        return None
    try:
        role = Role(role_value)
    except ValueError:
        return None

    content = data.get("content")
    if content is not None and not isinstance(content, str):
        return None

    tool_calls_raw = data.get("tool_calls")
    tool_calls: list[ToolCall] | None = None
    if tool_calls_raw is not None:
        if not isinstance(tool_calls_raw, list):
            return None
        parsed: list[ToolCall] = []
        for item in tool_calls_raw:
            if not isinstance(item, Mapping):
                return None
            call_id = item.get("id")
            name = item.get("name")
            arguments = item.get("arguments")
            if not isinstance(call_id, str) or not isinstance(name, str):
                return None
            if not isinstance(arguments, dict):
                return None
            parsed.append(ToolCall(id=call_id, name=name, arguments=arguments))
        tool_calls = parsed

    tool_call_id = data.get("tool_call_id")
    tool_name = data.get("tool_name")
    if tool_call_id is not None and not isinstance(tool_call_id, str):
        return None
    if tool_name is not None and not isinstance(tool_name, str):
        return None

    return Message(
        role=role,
        content=content,
        tool_calls=tool_calls,
        tool_call_id=tool_call_id,
        tool_name=tool_name if isinstance(tool_name, str) else None,
    )


def messages_from_turn_result(result: Mapping[str, object]) -> list[Message]:
    turn_messages = result.get("turn_messages")
    if not isinstance(turn_messages, Mapping):
        return []
    raw_messages = turn_messages.get("messages")
    if not isinstance(raw_messages, list):
        return []

    messages: list[Message] = []
    for item in raw_messages:
        if not isinstance(item, Mapping):
            continue
        message = _message_from_mapping(item)
        if message is not None:
            messages.append(message)
    return messages


def conversation_from_turn_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    newest_first: bool = True,
) -> Conversation:
    """Rebuild conversation history from persisted agent turn rows."""
    ordered = list(rows)
    if newest_first:
        ordered.reverse()
    messages: list[Message] = []
    for row in ordered:
        result = row.get("result")
        if isinstance(result, Mapping):
            messages.extend(messages_from_turn_result(result))
    return Conversation(messages=messages)
