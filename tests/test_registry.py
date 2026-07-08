"""Tests for lakegen.tool.registry.ToolRegistry."""

import pytest

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.tool.model import ToolParams
from lakegen.tool.registry import ToolRegistry


# ---------------------------------------------------------------------------
# Minimal params model that satisfies the ToolParams protocol
# ---------------------------------------------------------------------------

class _Params:
    @staticmethod
    def model_validate(data):
        return data

    @staticmethod
    def model_json_schema():
        return {"type": "object", "properties": {}}


def _make_registry() -> ToolRegistry:
    return ToolRegistry()


def _noop_handler(params):
    return None


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_register_and_retrieve():
    reg = _make_registry()
    reg.register(
        "mytoolset",
        "my_tool",
        description="does things",
        params_model=_Params,
        handler=_noop_handler,
    )
    defn = reg.get_tool_definition("mytoolset", "my_tool")
    assert defn.name == "my_tool"
    assert defn.description == "does things"


def test_register_bad_params_model_raises_type_error():
    reg = _make_registry()

    class _Bad:
        pass

    with pytest.raises(TypeError, match="model_validate"):
        reg.register(
            "ts",
            "bad_tool",
            description="x",
            params_model=_Bad,
            handler=_noop_handler,
        )


def test_register_overwrites_existing():
    reg = _make_registry()
    reg.register("ts", "t", description="v1", params_model=_Params, handler=_noop_handler)
    reg.register("ts", "t", description="v2", params_model=_Params, handler=_noop_handler)
    assert reg.get_tool_definition("ts", "t").description == "v2"


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def test_get_tool_definition_unknown_tool_raises_not_found():
    reg = _make_registry()
    reg.register("ts", "real", description="x", params_model=_Params, handler=_noop_handler)
    with pytest.raises(BaseError) as exc_info:
        reg.get_tool_definition("ts", "ghost")
    assert exc_info.value.code == ErrorCode.NOT_FOUND


def test_get_tool_definition_empty_name_raises_invalid():
    reg = _make_registry()
    with pytest.raises(BaseError) as exc_info:
        reg.get_tool_definition("ts", "")
    assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT


def test_get_tool_schema_returns_dict():
    reg = _make_registry()
    reg.register("ts", "t", description="desc", params_model=_Params, handler=_noop_handler)
    schema = reg.get_tool_schema("ts", "t")
    assert schema["name"] == "t"
    assert schema["description"] == "desc"
    assert "params" in schema


def test_list_tool_names():
    reg = _make_registry()
    reg.register("ts", "a", description="x", params_model=_Params, handler=_noop_handler)
    reg.register("ts", "b", description="y", params_model=_Params, handler=_noop_handler)
    names = reg.list_tool_names()
    assert set(names) == {"a", "b"}


def test_get_tools_description_by_toolset():
    reg = _make_registry()
    reg.register("ts1", "t1", description="d1", params_model=_Params, handler=_noop_handler)
    reg.register("ts2", "t2", description="d2", params_model=_Params, handler=_noop_handler)
    descs = reg.get_tools_description("ts1")
    assert "t1" in descs
    assert "t2" not in descs


def test_get_tools_description_unknown_toolset_raises_not_found():
    reg = _make_registry()
    with pytest.raises(BaseError) as exc_info:
        reg.get_tools_description("ghost")
    assert exc_info.value.code == ErrorCode.NOT_FOUND


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
