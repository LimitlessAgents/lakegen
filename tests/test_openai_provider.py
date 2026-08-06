"""Tests for lakegen.inference.providers.openai._OpenAI."""

from types import SimpleNamespace

import httpx
import openai
import pytest

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.inference.model import ChatRequest, Message, Role
from lakegen.inference.providers.openai import _OpenAI


def _request() -> ChatRequest:
    return ChatRequest(
        model="gpt-test",
        system_prompt="system",
        messages=[Message(role=Role.USER, content="hello")],
        tools=[],
    )


def _http_request() -> httpx.Request:
    return httpx.Request("POST", "https://api.openai.com/v1/responses")


def _status_error(
    exc_type,
    status: int,
    *,
    request_id: str = "req-123",
):
    request = _http_request()
    response = httpx.Response(status, request=request, headers={"x-request-id": request_id})
    return exc_type("boom", response=response, body={"error": {"message": "secret"}})


@pytest.fixture
def provider():
    return _OpenAI()


def test_client_disables_sdk_retries(mocker):
    openai_cls = mocker.patch("openai.OpenAI")
    provider = _OpenAI()

    provider._get_client()

    openai_cls.assert_called_once_with(max_retries=0)


def test_complete_forwards_timeout(provider, mocker):
    client = mocker.Mock()
    client.responses.create.return_value = SimpleNamespace(
        output=[],
        output_text="hello",
        usage=None,
    )
    provider.client = client

    provider.complete(_request(), inactivity_timeout=17.5)

    assert client.responses.create.call_args.kwargs["timeout"] == 17.5


def test_stream_forwards_timeout(provider, mocker):
    client = mocker.Mock()
    client.responses.create.return_value = iter(())
    provider.client = client

    list(provider.stream(_request(), inactivity_timeout=21.0))

    assert client.responses.create.call_args.kwargs["timeout"] == 21.0
    assert client.responses.create.call_args.kwargs["stream"] is True


@pytest.mark.parametrize(
    ("error", "code", "retryable", "user_fixable"),
    [
        (
            _status_error(openai.NotFoundError, 404),
            ErrorCode.MODEL_NOT_FOUND,
            False,
            True,
        ),
        (
            _status_error(openai.RateLimitError, 429),
            ErrorCode.RATE_LIMITED,
            True,
            False,
        ),
        (
            openai.APITimeoutError(_http_request()),
            ErrorCode.INFERENCE_FAILED,
            True,
            False,
        ),
        (
            openai.APIConnectionError(
                message="connection reset",
                request=_http_request(),
            ),
            ErrorCode.INFERENCE_FAILED,
            True,
            False,
        ),
        (
            _status_error(openai.InternalServerError, 500),
            ErrorCode.INFERENCE_FAILED,
            True,
            False,
        ),
        (
            _status_error(openai.BadRequestError, 400),
            ErrorCode.INFERENCE_FAILED,
            False,
            True,
        ),
        (
            _status_error(openai.AuthenticationError, 401),
            ErrorCode.INFERENCE_FAILED,
            False,
            True,
        ),
    ],
)
def test_maps_sdk_errors(provider, error, code, retryable, user_fixable):
    mapped = provider._map_error(error, "gpt-test")

    assert mapped.code == code
    assert mapped.is_retryable is retryable
    assert mapped.is_user_fixable is user_fixable
    assert mapped.details["provider"] == "openai"
    assert mapped.details["model"] == "gpt-test"


def test_maps_status_details_without_response_body(provider):
    error = _status_error(openai.RateLimitError, 429, request_id="req-999")

    mapped = provider._map_error(error, "gpt-test")

    assert mapped.details == {
        "provider": "openai",
        "model": "gpt-test",
        "status": 429,
        "request_id": "req-999",
    }
    assert "secret" not in str(mapped.details)


def test_complete_preserves_sdk_cause(provider, mocker):
    client = mocker.Mock()
    client.responses.create.side_effect = _status_error(openai.RateLimitError, 429)
    provider.client = client

    with pytest.raises(BaseError) as exc_info:
        provider.complete(_request(), inactivity_timeout=10.0)

    err = exc_info.value
    assert err.code == ErrorCode.RATE_LIMITED
    assert isinstance(err.__cause__, openai.RateLimitError)


def test_stream_preserves_sdk_cause(provider, mocker):
    client = mocker.Mock()
    client.responses.create.side_effect = openai.APITimeoutError(_http_request())
    provider.client = client

    with pytest.raises(BaseError) as exc_info:
        list(provider.stream(_request(), inactivity_timeout=10.0))

    err = exc_info.value
    assert err.code == ErrorCode.INFERENCE_FAILED
    assert err.is_retryable is True
    assert isinstance(err.__cause__, openai.APITimeoutError)
