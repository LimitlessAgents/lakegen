"""Tests for default agent prompt wiring."""

import threading
from dataclasses import replace
from unittest.mock import MagicMock

from lakegen.agent.loop import AgentLoop
from lakegen.agent.model import AgentConfig, Conversation
from lakegen.inference.model import StreamChunk
from lakegen.prompt import PROMPT
from lakegen.prompt.system_prompt import PROMPT as SYSTEM_PROMPT
from lakegen.session import Environment, SessionManager
from lakegen.tool.runtime import ToolRuntime


def test_prompt_reexported_from_package():
    assert PROMPT is SYSTEM_PROMPT
    assert "LakeGen" in PROMPT
    assert "Iceberg" in PROMPT


def test_build_prompt_composes_identity_and_catalog():
    loop = AgentLoop()
    config = AgentConfig(
        model="test",
        system_prompt="identity-only",
        provider="fake",
        max_turns=1,
    )
    built = loop._build_prompt(config, "prod")
    assert built.startswith("identity-only\n\n")
    assert "Active catalog: 'prod'" in built
    assert "Do not ask which catalog to use." in built


class _CapturingRouter:
    def __init__(self) -> None:
        self.last_system_prompt: str | None = None

    def complete(self, provider: str, request) -> None:
        raise AssertionError("complete should not be used")

    def stream(self, provider: str, request, *, cancel_event: threading.Event):
        self.last_system_prompt = request.system_prompt
        yield StreamChunk(text="ok")
        yield StreamChunk(done=True)


class _NoTools(ToolRuntime):
    def list_definitions(self):
        return []

    def dispatch(self, tools_to_call, *, catalog_name, cancel_event=None):
        return []


def test_invoke_sends_composed_system_prompt_to_model():
    router = _CapturingRouter()
    loop = AgentLoop(router=router, tool_runtime=_NoTools())
    config = AgentConfig(
        model="test-model",
        system_prompt="base",
        provider="fake",
        max_turns=3,
    )
    loop.invoke(
        config,
        Conversation(),
        "hi",
        catalog_name="analytics",
        stream=True,
        cancel_event=threading.Event(),
    )
    assert router.last_system_prompt == loop._build_prompt(config, "analytics")


def _test_env():
    catalogs = MagicMock()
    return replace(
        Environment.default(),
        catalog_service=catalogs,
        persistence=MagicMock(),
        session_repository=MagicMock(),
        agent_turn_repository=MagicMock(),
    )


def test_session_default_config_uses_product_prompt():
    mgr = SessionManager(env=_test_env())
    from tests.conftest import open_session

    session = open_session(mgr, owner_id="user-1", catalog_name="prod")
    assert session.state.config.system_prompt == PROMPT
