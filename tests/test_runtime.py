"""Tests for lakegen.tool.runtime.ToolRuntime."""

from unittest.mock import patch

from pydantic import BaseModel

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.tool.model import ToolCall
from lakegen.tool.registry import ToolRegistry
from lakegen.tool.runtime import ToolRuntime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _SimpleArguments(BaseModel):
    value: str


def _make_runtime_with_tool(handler, *, name="my_tool"):
    """Return a (ToolRuntime, name) wired with a single tool on an isolated registry."""
    reg = ToolRegistry()
    reg.register(
        name,
        description="test tool",
        arguments_model=_SimpleArguments,
        handler=handler,
    )
    rt = ToolRuntime()
    return rt, reg, name


def _run(rt: ToolRuntime, reg: ToolRegistry, name: str, arguments):
    with patch("lakegen.tool.runtime.registry", reg):
        return rt._run_one(ToolCall(id="call_1", name=name, arguments=arguments))


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------

def test_use_tool_success():
    def handler(arguments: _SimpleArguments):
        return {"echo": arguments.value}

    rt, reg, name = _make_runtime_with_tool(handler)
    out = _run(rt, reg, name, {"value": "hello"})
    assert out.ok is True
    assert out.response == {"echo": "hello"}
    assert out.tool_name == name


def test_dispatch_returns_list():
    def handler(arguments: _SimpleArguments):
        return {"echo": arguments.value}

    rt, reg, name = _make_runtime_with_tool(handler)
    with patch("lakegen.tool.runtime.registry", reg):
        results = rt.dispatch([ToolCall(id="call_1", name=name, arguments={"value": "hi"})])
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0].ok is True


def test_dispatch_empty_returns_empty():
    rt = ToolRuntime()
    assert rt.dispatch([]) == []


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

def test_validation_error_returns_invalid_argument():
    def handler(arguments: _SimpleArguments):
        return {}

    rt, reg, name = _make_runtime_with_tool(handler)
    out = _run(rt, reg, name, {"value": None})
    assert out.ok is False
    assert out.error["code"] == ErrorCode.INVALID_ARGUMENT.value


def test_base_error_from_handler_is_captured():
    def handler(arguments: _SimpleArguments):
        raise BaseError(ErrorCode.NOT_FOUND, "resource missing")

    rt, reg, name = _make_runtime_with_tool(handler)
    out = _run(rt, reg, name, {"value": "x"})
    assert out.ok is False
    assert out.error["code"] == "NOT_FOUND"


def test_unexpected_exception_wrapped_as_internal():
    def handler(arguments: _SimpleArguments):
        raise RuntimeError("something exploded")

    rt, reg, name = _make_runtime_with_tool(handler)
    out = _run(rt, reg, name, {"value": "x"})
    assert out.ok is False
    assert out.error["code"] == "INTERNAL"


def test_non_serializable_result_caught():
    class _Unserializable:
        pass

    def handler(arguments: _SimpleArguments):
        return _Unserializable()

    rt, reg, name = _make_runtime_with_tool(handler)
    out = _run(rt, reg, name, {"value": "x"})
    assert out.ok is False
    assert out.error["code"] == "INTERNAL"
    assert "non-serializable" in out.error["message"]


def test_non_dict_arguments_returns_invalid_type():
    rt, reg, name = _make_runtime_with_tool(lambda a: {})
    out = _run(rt, reg, name, "not-a-dict")
    assert out.ok is False
    assert out.error["code"] == "INVALID_TYPE"
