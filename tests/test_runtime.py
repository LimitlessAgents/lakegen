"""Tests for lakegen.tool.runtime.ToolRuntime."""

from unittest.mock import MagicMock

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
    rt = ToolRuntime(registry=reg)
    return rt, name


def _run(rt: ToolRuntime, name: str, arguments):
    return rt._run_one(
        ToolCall(id="call_1", name=name, arguments=arguments),
        catalog_name="prod",
    )


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------

def test_use_tool_success():
    def handler(arguments: _SimpleArguments):
        return {"echo": arguments.value}

    rt, name = _make_runtime_with_tool(handler)
    out = _run(rt, name, {"value": "hello"})
    assert out.ok is True
    assert out.response == {"echo": "hello"}
    assert out.tool_name == name


def test_dispatch_returns_list():
    def handler(arguments: _SimpleArguments):
        return {"echo": arguments.value}

    rt, name = _make_runtime_with_tool(handler)
    results = rt.dispatch(
        [ToolCall(id="call_1", name=name, arguments={"value": "hi"})],
        catalog_name="prod",
    )
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0].ok is True


def test_dispatch_empty_returns_empty():
    rt = ToolRuntime()
    assert rt.dispatch([], catalog_name="prod") == []


def test_dispatch_injects_catalog_name():
    from lakegen.tool.iceberg.model import CatalogConnectionArguments

    seen = {}

    def handler(arguments: CatalogConnectionArguments):
        seen["name"] = arguments.name
        return {"ok": True}

    reg = ToolRegistry()
    reg.register(
        "list_namespaces",
        description="test",
        arguments_model=CatalogConnectionArguments,
        handler=handler,
    )
    rt = ToolRuntime(registry=reg)
    out = rt.dispatch(
        [ToolCall(id="c1", name="list_namespaces", arguments={})],
        catalog_name="prod",
    )
    assert out[0].ok is True
    assert seen["name"] == "prod"


def test_dispatch_injects_catalog_connection():
    catalogs = MagicMock()
    connection = catalogs.get_connection.return_value
    seen = {}

    def handler(arguments: _SimpleArguments, catalog):
        seen["catalog"] = catalog
        return {"ok": True}

    registry = ToolRegistry()
    registry.register(
        "catalog_tool",
        description="test",
        arguments_model=_SimpleArguments,
        handler=handler,
        requires_catalog=True,
    )
    runtime = ToolRuntime(registry=registry, catalogs=catalogs)

    output = runtime.dispatch(
        [ToolCall(id="c1", name="catalog_tool", arguments={"value": "x"})],
        catalog_name="prod",
    )

    assert output[0].ok is True
    catalogs.get_connection.assert_called_once_with("prod")
    assert seen["catalog"] is connection


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

def test_validation_error_returns_invalid_argument():
    def handler(arguments: _SimpleArguments):
        return {}

    rt, name = _make_runtime_with_tool(handler)
    out = _run(rt, name, {"value": None})
    assert out.ok is False
    assert out.error["code"] == ErrorCode.INVALID_ARGUMENT.value


def test_base_error_from_handler_is_captured():
    def handler(arguments: _SimpleArguments):
        raise BaseError(ErrorCode.NOT_FOUND, "resource missing")

    rt, name = _make_runtime_with_tool(handler)
    out = _run(rt, name, {"value": "x"})
    assert out.ok is False
    assert out.error["code"] == "NOT_FOUND"


def test_unexpected_exception_wrapped_as_internal():
    def handler(arguments: _SimpleArguments):
        raise RuntimeError("something exploded")

    rt, name = _make_runtime_with_tool(handler)
    out = _run(rt, name, {"value": "x"})
    assert out.ok is False
    assert out.error["code"] == "INTERNAL"


def test_non_serializable_result_caught():
    class _Unserializable:
        pass

    def handler(arguments: _SimpleArguments):
        return _Unserializable()

    rt, name = _make_runtime_with_tool(handler)
    out = _run(rt, name, {"value": "x"})
    assert out.ok is False
    assert out.error["code"] == "INTERNAL"
    assert "non-serializable" in out.error["message"]


def test_dispatch_stops_remaining_tools_on_cancel():
    import threading

    calls: list[str] = []

    def handler(arguments: _SimpleArguments):
        calls.append(arguments.value)
        return {"echo": arguments.value}

    rt, name = _make_runtime_with_tool(handler)
    cancel_event = threading.Event()
    cancel_event.set()
    results = rt.dispatch(
        [
            ToolCall(id="c1", name=name, arguments={"value": "one"}),
            ToolCall(id="c2", name=name, arguments={"value": "two"}),
        ],
        catalog_name="prod",
        cancel_event=cancel_event,
    )
    assert results == []
    assert calls == []


def test_dispatch_runs_until_cancel():
    import threading

    calls: list[str] = []
    cancel_event = threading.Event()

    def handler(arguments: _SimpleArguments):
        calls.append(arguments.value)
        cancel_event.set()
        return {"echo": arguments.value}

    rt, name = _make_runtime_with_tool(handler)
    results = rt.dispatch(
        [
            ToolCall(id="c1", name=name, arguments={"value": "one"}),
            ToolCall(id="c2", name=name, arguments={"value": "two"}),
        ],
        catalog_name="prod",
        cancel_event=cancel_event,
    )
    assert len(results) == 1
    assert calls == ["one"]



def test_non_dict_arguments_returns_invalid_type():
    rt, name = _make_runtime_with_tool(lambda a: {})
    out = _run(rt, name, "not-a-dict")
    assert out.ok is False
    assert out.error["code"] == "INVALID_TYPE"
