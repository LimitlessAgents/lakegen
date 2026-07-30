"""Tests for lakegen.tool.registry.ToolRegistry."""

import pytest

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.tool.registry import ToolRegistry


# ---------------------------------------------------------------------------
# Minimal arguments model that satisfies the ToolArguments protocol
# ---------------------------------------------------------------------------

class _Arguments:
    @staticmethod
    def model_validate(data):
        return data

    @staticmethod
    def model_json_schema():
        return {"type": "object", "properties": {}}


def _make_registry() -> ToolRegistry:
    return ToolRegistry()


def _noop_handler(arguments):
    return None


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_register_and_retrieve():
    reg = _make_registry()
    reg.register(
        "my_tool",
        description="does things",
        arguments_model=_Arguments,
        handler=_noop_handler,
    )
    defn = reg.get_tool_definition("my_tool")
    assert defn.name == "my_tool"
    assert defn.description == "does things"


def test_register_bad_arguments_model_raises_type_error():
    reg = _make_registry()

    class _Bad:
        pass

    with pytest.raises(TypeError, match="model_validate"):
        reg.register(
            "bad_tool",
            description="x",
            arguments_model=_Bad,
            handler=_noop_handler,
        )


def test_register_overwrites_existing():
    reg = _make_registry()
    reg.register("t", description="v1", arguments_model=_Arguments, handler=_noop_handler)
    reg.register("t", description="v2", arguments_model=_Arguments, handler=_noop_handler)
    assert reg.get_tool_definition("t").description == "v2"


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def test_get_tool_definition_unknown_tool_raises_not_found():
    reg = _make_registry()
    reg.register("real", description="x", arguments_model=_Arguments, handler=_noop_handler)
    with pytest.raises(BaseError) as exc_info:
        reg.get_tool_definition("ghost")
    assert exc_info.value.code == ErrorCode.NOT_FOUND


def test_get_tool_definition_empty_name_raises_invalid():
    reg = _make_registry()
    with pytest.raises(BaseError) as exc_info:
        reg.get_tool_definition("")
    assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT


def test_list_tool_names():
    reg = _make_registry()
    reg.register("a", description="x", arguments_model=_Arguments, handler=_noop_handler)
    reg.register("b", description="y", arguments_model=_Arguments, handler=_noop_handler)
    names = reg.list_tool_names()
    assert set(names) == {"a", "b"}


def test_get_all_tools_info():
    reg = _make_registry()
    reg.register("t1", description="d1", arguments_model=_Arguments, handler=_noop_handler)
    reg.register("t2", description="d2", arguments_model=_Arguments, handler=_noop_handler)
    tools = reg.get_all_tools_info()
    assert set(tools) == {"t1", "t2"}
    assert tools["t1"].description == "d1"


# ---------------------------------------------------------------------------
# Discovery integration: all expected tools are registered at import time
# ---------------------------------------------------------------------------

def test_discovery_registers_catalog_tools():
    """Importing lakegen.tool triggers discover_tools(); all iceberg tools present."""
    import lakegen.tool  # noqa: F401 — side-effect import
    from lakegen.tool.registry import registry

    names = registry.list_tool_names()
    assert "add_catalog" in names
    assert "list_namespaces" in names
    assert "list_tables" in names
