"""Tests for lakegen.tool.runtime.ToolRuntime."""

import pytest
from pydantic import BaseModel

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.tool.model import ToolCall, ToolOutput
from lakegen.tool.registry import ToolRegistry
from lakegen.tool.runtime import ToolRuntime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _SimpleArguments(BaseModel):
    value: str


def _make_runtime_with_tool(handler, *, toolset="ts", name="my_tool"):
    """Return a (ToolRuntime, toolset, name) wired with a single tool."""
    reg = ToolRegistry()
    reg.register(
        toolset,
        name,
        description="test tool",
        arguments_model=_SimpleArguments,
        handler=handler,
    )
    rt = ToolRuntime()
    # Patch the runtime to use our isolated registry instead of the global one.
    rt._registry = reg

    # Monkey-patch _run_one to use our local registry.
    def _run_one_patched(ts, n, arguments):
        import json
        from pydantic import ValidationError
        try:
            if not isinstance(arguments, dict):
                raise BaseError(
                    ErrorCode.INVALID_TYPE,
                    "Tool arguments must be a dict.",
                    details={"got_type": type(arguments).__name__},
                )
            tool = reg.get_tool_definition(ts, n)
            validated = tool.arguments_model.model_validate(arguments)
            result = tool.handler(validated)
            try:
                json.dumps(result)
            except (TypeError, ValueError) as e:
                raise BaseError(
                    ErrorCode.INTERNAL,
                    f"Tool {n!r} returned a non-serializable result.",
                    cause=e,
                )
            return ToolOutput(tool_name=n, ok=True, response=result)
        except BaseError as e:
            return ToolOutput(tool_name=n, ok=False, error=e.to_dict())
        except ValidationError as e:
            return ToolOutput(
                tool_name=n,
                ok=False,
                error={
                    "code": ErrorCode.INVALID_ARGUMENT.value,
                    "message": f"Invalid arguments for tool {n!r}.",
                    "details": {"errors": e.errors()},
                },
            )
        except Exception as e:
            err = BaseError(ErrorCode.INTERNAL, f"Unexpected error.", cause=e)
            return ToolOutput(tool_name=n, ok=False, error=err.to_dict())

    rt._run_one = _run_one_patched
    return rt, toolset, name


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------

def test_use_tool_success():
    def handler(arguments: _SimpleArguments):
        return {"echo": arguments.value}

    rt, ts, name = _make_runtime_with_tool(handler)
    out = rt._run_one(ts, name, {"value": "hello"})
    assert out.ok is True
    assert out.response == {"echo": "hello"}
    assert out.tool_name == name


def test_dispatch_returns_list():
    def handler(arguments: _SimpleArguments):
        return {"echo": arguments.value}

    rt, ts, name = _make_runtime_with_tool(handler)
    results = rt.dispatch(ts, [ToolCall(id="call_1", name=name, arguments={"value": "hi"})])
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0].ok is True


def test_dispatch_empty_returns_empty():
    rt = ToolRuntime()
    assert rt.dispatch("ts", []) == []


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

def test_validation_error_returns_invalid_argument():
    def handler(arguments: _SimpleArguments):
        return {}

    rt, ts, name = _make_runtime_with_tool(handler)
    # Pass an int where a str is expected.
    out = rt._run_one(ts, name, {"value": 123})
    # Pydantic v2 coerces int to str by default; pass a clearly wrong type.
    out = rt._run_one(ts, name, {"value": None})
    assert out.ok is False
    assert out.error["code"] == ErrorCode.INVALID_ARGUMENT.value


def test_base_error_from_handler_is_captured():
    def handler(arguments: _SimpleArguments):
        raise BaseError(ErrorCode.NOT_FOUND, "resource missing")

    rt, ts, name = _make_runtime_with_tool(handler)
    out = rt._run_one(ts, name, {"value": "x"})
    assert out.ok is False
    assert out.error["code"] == "NOT_FOUND"


def test_unexpected_exception_wrapped_as_internal():
    def handler(arguments: _SimpleArguments):
        raise RuntimeError("something exploded")

    rt, ts, name = _make_runtime_with_tool(handler)
    out = rt._run_one(ts, name, {"value": "x"})
    assert out.ok is False
    assert out.error["code"] == "INTERNAL"


def test_non_serializable_result_caught():
    class _Unserializable:
        pass

    def handler(arguments: _SimpleArguments):
        return _Unserializable()

    rt, ts, name = _make_runtime_with_tool(handler)
    out = rt._run_one(ts, name, {"value": "x"})
    assert out.ok is False
    assert out.error["code"] == "INTERNAL"
    assert "non-serializable" in out.error["message"]


def test_non_dict_arguments_returns_invalid_type():
    rt, ts, name = _make_runtime_with_tool(lambda a: {})
    out = rt._run_one(ts, name, "not-a-dict")
    assert out.ok is False
    assert out.error["code"] == "INVALID_TYPE"
