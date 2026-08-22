"""Tests for lakegen.inference.providers.openai._OpenAI."""

from types import SimpleNamespace
import threading

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
    retry_after: str | None = None,
):
    request = _http_request()
    headers = {"x-request-id": request_id}
    if retry_after is not None:
        headers["retry-after"] = retry_after
    response = httpx.Response(status, request=request, headers=headers)
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

    list(provider.stream(_request(), inactivity_timeout=21.0, cancel_event=threading.Event()))

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


def test_maps_numeric_retry_after(provider):
    error = _status_error(openai.RateLimitError, 429, retry_after="12")

    mapped = provider._map_error(error, "gpt-test")

    assert mapped.details["retry_after"] == 12.0


def test_ignores_non_numeric_retry_after(provider):
    error = _status_error(
        openai.RateLimitError,
        429,
        retry_after="Wed, 21 Oct 2015 07:28:00 GMT",
    )

    mapped = provider._map_error(error, "gpt-test")

    assert "retry_after" not in mapped.details


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
        list(provider.stream(_request(), inactivity_timeout=10.0, cancel_event=threading.Event()))

    err = exc_info.value
    assert err.code == ErrorCode.INFERENCE_FAILED
    assert err.is_retryable is True
    assert isinstance(err.__cause__, openai.APITimeoutError)


def test_stream_stops_and_closes_on_cancel(provider):
    cancel_event = threading.Event()

    class _Stream:
        def __init__(self) -> None:
            self.closed = False
            self._n = 0

        def __iter__(self):
            return self

        def __next__(self):
            self._n += 1
            if self._n == 1:
                return SimpleNamespace(type="response.output_text.delta", delta="a")
            if self._n == 2:
                cancel_event.set()
                return SimpleNamespace(type="response.output_text.delta", delta="b")
            if self._n == 3:
                return SimpleNamespace(
                    type="response.completed",
                    response=SimpleNamespace(usage=None),
                )
            raise StopIteration

        def close(self) -> None:
            self.closed = True

    stream = _Stream()
    provider.client = SimpleNamespace(
        responses=SimpleNamespace(create=lambda **kwargs: stream)
    )

    chunks = list(
        provider.stream(
            _request(),
            inactivity_timeout=10.0,
            cancel_event=cancel_event,
        )
    )

    assert [c.text for c in chunks] == ["a"]
    assert stream.closed is True


def test_stream_close_unblocks_blocked_next(provider):
    started = threading.Event()
    cancel_event = threading.Event()

    class _Stream:
        def __init__(self) -> None:
            self.closed = False
            self._gate = threading.Event()

        def __iter__(self):
            return self

        def __next__(self):
            started.set()
            if not self._gate.wait(timeout=5):
                raise TimeoutError("stream was not closed")
            raise StopIteration

        def close(self) -> None:
            self.closed = True
            self._gate.set()

    stream = _Stream()
    provider.client = SimpleNamespace(
        responses=SimpleNamespace(create=lambda **kwargs: stream)
    )

    def consume() -> None:
        list(
            provider.stream(
                _request(),
                inactivity_timeout=10.0,
                cancel_event=cancel_event,
            )
        )

    worker = threading.Thread(target=consume)
    worker.start()
    assert started.wait(timeout=2)
    cancel_event.set()
    worker.join(timeout=2)
    assert worker.is_alive() is False
    assert stream.closed is True
