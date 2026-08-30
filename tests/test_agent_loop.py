"""Tests for lakegen.agent.loop.AgentLoop cancel and completion."""

from collections.abc import Iterator
import threading

import pytest

from lakegen.agent.loop import AgentLoop
from lakegen.agent.model import (
    AgentConfig,
    AgentLoopFailure,
    Conversation,
    StopReason,
)
from lakegen.inference.model import (
    ChatRequest,
    ChatResponse,
    Message,
    Role,
    StreamChunk,
)
from lakegen.tool.model import ToolCall, ToolOutput
from lakegen.tool.runtime import ToolRuntime


def _config(*, max_turns: int = 3) -> AgentConfig:
    return AgentConfig(
        model="test-model",
        system_prompt="test",
        provider="fake",
        max_turns=max_turns,
    )


class _FakeRouter:
    def __init__(self, chunks: list[StreamChunk] | None = None) -> None:
        self.chunks = chunks if chunks is not None else [
            StreamChunk(text="hello"),
            StreamChunk(done=True),
        ]
        self.stream_calls = 0

    def complete(self, provider: str, request: ChatRequest) -> ChatResponse:
        raise AssertionError("complete should not be used")

    def stream(
        self,
        provider: str,
        request: ChatRequest,
        *,
        cancel_event: threading.Event,
    ) -> Iterator[StreamChunk]:
        self.stream_calls += 1
        yield from self.chunks


class _FakeTools(ToolRuntime):
    def __init__(self) -> None:
        self.dispatch_calls = 0

    def list_definitions(self):
        return []

    def dispatch(self, tools_to_call, *, catalog_name, cancel_event=None):
        self.dispatch_calls += 1
        return [
            ToolOutput(
                tool_name=call.name,
                tool_call_id=call.id,
                ok=True,
                response={"ok": True},
            )
            for call in tools_to_call
        ]


def test_completed_text_response():
    loop = AgentLoop(router=_FakeRouter(), tool_runtime=_FakeTools())
    existing = Message(role=Role.ASSISTANT, content="earlier")
    conversation = Conversation(messages=[existing])
    result = loop.invoke(
        _config(),
        conversation,
        "hi",
        catalog_name="prod",
        stream=True,
        cancel_event=threading.Event(),
    )
    assert result.stop_reason is StopReason.COMPLETED
    assert result.final_message == "hello"
    assert conversation.messages == [existing]
    assert [message.role for message in result.turn_messages.messages] == [
        Role.USER,
        Role.ASSISTANT,
    ]


def test_cancel_before_first_model_call():
    cancel_event = threading.Event()
    cancel_event.set()
    router = _FakeRouter()
    loop = AgentLoop(router=router, tool_runtime=_FakeTools())
    result = loop.invoke(
        _config(),
        Conversation(),
        "hi",
        catalog_name="prod",
        stream=True,
        cancel_event=cancel_event,
    )
    assert result.stop_reason is StopReason.CANCELLED
    assert router.stream_calls == 0
    assert result.final_message == ""
    assert result.turn_messages.messages[-1].role is Role.SYSTEM
    assert "stopped by the user" in result.turn_messages.messages[-1].content


def test_cancel_during_stream_preserves_visible_output():
    cancel_event = threading.Event()

    class _CancellingRouter(_FakeRouter):
        def stream(self, provider, request, *, cancel_event):
            self.stream_calls += 1
            yield StreamChunk(text="partial")
            cancel_event.set()
            yield StreamChunk(text="more")
            yield StreamChunk(done=True)

    loop = AgentLoop(router=_CancellingRouter(), tool_runtime=_FakeTools())
    conversation = Conversation()
    result = loop.invoke(
        _config(),
        conversation,
        "hi",
        catalog_name="prod",
        stream=True,
        cancel_event=cancel_event,
    )
    assert result.stop_reason is StopReason.CANCELLED
    assert conversation.messages == []
    roles = [m.role for m in result.turn_messages.messages]
    assert roles == [Role.USER, Role.ASSISTANT, Role.SYSTEM]
    assert result.turn_messages.messages[1].content == "partial"


def test_cancel_skips_tools_after_tool_call():
    cancel_event = threading.Event()
    tools = _FakeTools()

    class _ToolRouter(_FakeRouter):
        def stream(self, provider, request, *, cancel_event):
            self.stream_calls += 1
            yield StreamChunk(
                done=True,
                tool_calls=[ToolCall(id="c1", name="list_tables", arguments={})],
            )
            cancel_event.set()

    loop = AgentLoop(router=_ToolRouter(), tool_runtime=tools)
    result = loop.invoke(
        _config(),
        Conversation(),
        "hi",
        catalog_name="prod",
        stream=True,
        cancel_event=cancel_event,
    )
    assert result.stop_reason is StopReason.CANCELLED
    assert tools.dispatch_calls == 0
    assert [message.role for message in result.turn_messages.messages] == [
        Role.USER,
        Role.ASSISTANT,
        Role.TOOL,
        Role.SYSTEM,
    ]
    synthetic_result = result.turn_messages.messages[-2]
    assert synthetic_result.tool_call_id == "c1"
    assert '"ok": false' in synthetic_result.content


def test_max_iterations_adds_terminal_marker():
    tool_call = ToolCall(id="c1", name="list_tables", arguments={})
    loop = AgentLoop(
        router=_FakeRouter(chunks=[StreamChunk(done=True, tool_calls=[tool_call])]),
        tool_runtime=_FakeTools(),
    )

    result = loop.invoke(
        _config(max_turns=1),
        Conversation(),
        "hi",
        catalog_name="prod",
        stream=True,
        cancel_event=threading.Event(),
    )

    assert result.stop_reason is StopReason.MAX_ITERATIONS_EXCEEDED
    assert result.turn_messages.messages[-1].role is Role.SYSTEM
    assert "reaching 1 agent iteration" in result.turn_messages.messages[-1].content


def test_crash_preserves_visible_output_and_terminal_marker():
    class _CrashingRouter(_FakeRouter):
        def stream(self, provider, request, *, cancel_event):
            self.stream_calls += 1
            yield StreamChunk(text="partial")
            raise RuntimeError("provider disconnected")

    loop = AgentLoop(router=_CrashingRouter(), tool_runtime=_FakeTools())

    with pytest.raises(AgentLoopFailure) as exc_info:
        loop.invoke(
            _config(),
            Conversation(),
            "hi",
            catalog_name="prod",
            stream=True,
            cancel_event=threading.Event(),
        )

    failure = exc_info.value
    assert isinstance(failure.error, RuntimeError)
    assert failure.result.stop_reason is StopReason.INTERNAL_ERROR
    assert [message.role for message in failure.result.turn_messages.messages] == [
        Role.USER,
        Role.ASSISTANT,
        Role.SYSTEM,
    ]
    assert failure.result.turn_messages.messages[1].content == "partial"
    assert "crashed" in failure.result.turn_messages.messages[-1].content
