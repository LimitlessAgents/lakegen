from lakegen.agent.model import AgentLoopResult, Conversation, StopReason
from lakegen.agent.serialization import serialize_agent_loop_result
from lakegen.inference import Message, Role


def test_serialize_agent_loop_result() -> None:
    result = AgentLoopResult(
        final_message="done",
        turn_messages=Conversation(
            messages=[Message(role=Role.USER, content="hi")],
        ),
        stop_reason=StopReason.COMPLETED,
    )
    assert serialize_agent_loop_result(result) == {
        "final_message": "done",
        "turn_messages": {
            "messages": [
                {
                    "role": "user",
                    "content": "hi",
                    "tool_calls": None,
                    "tool_call_id": None,
                    "tool_name": None,
                }
            ]
        },
        "stop_reason": "completed",
    }
