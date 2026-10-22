"""Contract tests for lakegen.api.schema wire models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lakegen.agent import StopReason
from lakegen.api.run.runner import AgentEventType
from lakegen.api.schema import (
    CatalogResponse,
    ErrorBody,
    TextDeltaEvent,
    TurnDoneEvent,
    TurnRequest,
    stream_event_adapter,
)
from lakegen.core.error.code import ErrorCode


def test_catalog_response_has_no_secret_fields() -> None:
    fields = CatalogResponse.model_fields
    for secret in (
        "access_key",
        "secret_key",
        "token",
        "password",
        "credential",
        "glue_secret_key",
    ):
        assert secret not in fields


def test_turn_request_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        TurnRequest.model_validate({"text": ""})


def test_turn_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        TurnRequest.model_validate({"text": "hi", "stream": True})


def test_stream_text_delta() -> None:
    event = stream_event_adapter.validate_python(
        {"type": "text_delta", "data": {"text": "hello"}}
    )
    assert isinstance(event, TextDeltaEvent)
    assert event.data.text == "hello"
    assert event.type == AgentEventType.TEXT_DELTA


def test_stream_turn_done() -> None:
    event = stream_event_adapter.validate_python(
        {
            "type": "turn_done",
            "data": {"final_message": "hello", "stop_reason": "completed"},
        }
    )
    assert isinstance(event, TurnDoneEvent)
    assert event.data.stop_reason is StopReason.COMPLETED


def test_error_body_is_client_facing() -> None:
    body = ErrorBody(code=ErrorCode.NOT_FOUND, message="Catalog not found.")
    assert body.model_dump(mode="json") == {
        "code": "NOT_FOUND",
        "message": "Catalog not found.",
    }


def test_turn_request_default_model_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    request = TurnRequest.model_validate({"text": "hello"})
    assert request.model == "gpt-4o-mini"
    assert request.provider == "openai"


def test_turn_request_default_model_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    request = TurnRequest.model_validate({"text": "hello"})
    assert request.model == "gpt-4o"


def test_turn_request_explicit_model_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    request = TurnRequest.model_validate({"text": "hello", "model": "custom-override"})
    assert request.model == "custom-override"
