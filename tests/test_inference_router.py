"""Tests for lakegen.inference.router.Router."""

from collections.abc import Iterator

import pytest

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.inference.model import (
    ChatRequest,
    ChatResponse,
    Message,
    Role,
    StreamChunk,
)
from lakegen.inference.policy import InferencePolicy
from lakegen.inference.protocol import ProviderCapabilities
from lakegen.inference.registry import InferenceRegistry
from lakegen.inference.router import Router


def _request() -> ChatRequest:
    return ChatRequest(
        model="test-model",
        system_prompt="system",
        messages=[Message(role=Role.USER, content="hello")],
        tools=[],
    )


def _response(text: str = "ok") -> ChatResponse:
    return ChatResponse(message=Message(role=Role.ASSISTANT, content=text))


class FakeProvider:
    def __init__(
        self,
        *,
        complete=None,
        stream=None,
    ) -> None:
        self._complete = complete
        self._stream = stream
        self.complete_calls = 0
        self.stream_calls = 0

    @property
    def name(self) -> str:
        return "fake"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities()

    def complete(
        self,
        request: ChatRequest,
        *,
        inactivity_timeout: float,
    ) -> ChatResponse:
        self.complete_calls += 1
        if self._complete is not None:
            return self._complete(request, inactivity_timeout=inactivity_timeout)
        return _response()

    def stream(
        self,
        request: ChatRequest,
        *,
        inactivity_timeout: float,
    ) -> Iterator[StreamChunk]:
        self.stream_calls += 1
        if self._stream is not None:
            yield from self._stream(request, inactivity_timeout=inactivity_timeout)
            return
        yield StreamChunk(text="chunk")
        yield StreamChunk(done=True)


def _router(
    provider: FakeProvider,
    *,
    policy: InferencePolicy | None = None,
    delays: list[float] | None = None,
) -> Router:
    registry = InferenceRegistry()
    registry.register(provider)
    return Router(
        policy=policy,
        registry=registry,
        sleep=(delays.append if delays is not None else lambda _: None),
        random=lambda: 0.5,
    )


def test_unknown_provider_raises_not_found():
    router = Router(registry=InferenceRegistry())

    with pytest.raises(BaseError) as exc_info:
        router.complete("missing", _request())

    err = exc_info.value
    assert err.code == ErrorCode.NOT_FOUND
    assert err.is_retryable is False
    assert err.is_user_fixable is True
    assert err.details == {"provider": "missing"}


def test_wraps_unexpected_provider_exception_with_cause():
    def boom(request, *, inactivity_timeout):
        raise RuntimeError("provider blew up")

    provider = FakeProvider(complete=boom)
    router = _router(provider)

    with pytest.raises(BaseError) as exc_info:
        router.complete("fake", _request())

    err = exc_info.value
    assert err.code == ErrorCode.INFERENCE_FAILED
    assert err.is_retryable is False
    assert isinstance(err.__cause__, RuntimeError)
    assert str(err.__cause__) == "provider blew up"


def test_does_not_retry_user_fixable_errors():
    attempts = {"count": 0}

    def fail(request, *, inactivity_timeout):
        attempts["count"] += 1
        raise BaseError(
            ErrorCode.MODEL_NOT_FOUND,
            "bad model",
            is_retryable=False,
            is_user_fixable=True,
        )

    provider = FakeProvider(complete=fail)
    delays: list[float] = []
    router = _router(provider, delays=delays)

    with pytest.raises(BaseError) as exc_info:
        router.complete("fake", _request())

    assert exc_info.value.code == ErrorCode.MODEL_NOT_FOUND
    assert attempts["count"] == 1
    assert delays == []


def test_retries_retryable_errors_up_to_max_attempts():
    attempts = {"count": 0}

    def fail(request, *, inactivity_timeout):
        attempts["count"] += 1
        raise BaseError(
            ErrorCode.RATE_LIMITED,
            "slow down",
            is_retryable=True,
            is_user_fixable=False,
        )

    provider = FakeProvider(complete=fail)
    delays: list[float] = []
    router = _router(
        provider,
        policy=InferencePolicy(max_attempts=3, backoff_base=1.0, backoff_cap=8.0),
        delays=delays,
    )

    with pytest.raises(BaseError) as exc_info:
        router.complete("fake", _request())

    assert exc_info.value.code == ErrorCode.RATE_LIMITED
    assert attempts["count"] == 3
    assert delays == [0.5, 1.0]


def test_honors_retry_after_capped_by_backoff_cap():
    attempts = {"count": 0}

    def fail(request, *, inactivity_timeout):
        attempts["count"] += 1
        raise BaseError(
            ErrorCode.RATE_LIMITED,
            "slow down",
            is_retryable=True,
            is_user_fixable=False,
            details={"retry_after": 30},
        )

    provider = FakeProvider(complete=fail)
    delays: list[float] = []
    router = _router(
        provider,
        policy=InferencePolicy(max_attempts=2, backoff_base=0.5, backoff_cap=8.0),
        delays=delays,
    )

    with pytest.raises(BaseError):
        router.complete("fake", _request())

    assert attempts["count"] == 2
    # Prefer Retry-After, but never wait longer than backoff_cap.
    assert delays == [8.0]


def test_recovers_on_later_attempt():
    attempts = {"count": 0}

    def fail_once(request, *, inactivity_timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise BaseError(
                ErrorCode.INFERENCE_FAILED,
                "temporary",
                is_retryable=True,
                is_user_fixable=False,
            )
        return _response("recovered")

    provider = FakeProvider(complete=fail_once)
    delays: list[float] = []
    router = _router(provider, delays=delays)

    response = router.complete("fake", _request())

    assert response.message.content == "recovered"
    assert attempts["count"] == 2
    assert delays == [0.25]


def test_forwards_inactivity_timeout_to_provider():
    seen: dict[str, float] = {}

    def complete(request, *, inactivity_timeout):
        seen["timeout"] = inactivity_timeout
        return _response()

    provider = FakeProvider(complete=complete)
    router = _router(
        provider,
        policy=InferencePolicy(inactivity_timeout=42.0),
    )

    router.complete("fake", _request())

    assert seen["timeout"] == 42.0


def test_sequential_calls_keep_independent_attempt_state():
    first_router_call = {"active": True}

    def complete(request, *, inactivity_timeout):
        if first_router_call["active"]:
            raise BaseError(
                ErrorCode.RATE_LIMITED,
                "slow down",
                is_retryable=True,
                is_user_fixable=False,
            )
        return _response("second call")

    provider = FakeProvider(complete=complete)
    delays: list[float] = []
    router = _router(provider, delays=delays)

    with pytest.raises(BaseError):
        router.complete("fake", _request())

    first_router_call["active"] = False
    response = router.complete("fake", _request())

    assert response.message.content == "second call"
    assert provider.complete_calls == 4
    assert delays == [0.25, 0.5]


def test_stream_retries_before_first_chunk():
    attempts = {"count": 0}

    def fail_before_output(request, *, inactivity_timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise BaseError(
                ErrorCode.INFERENCE_FAILED,
                "stream start failed",
                is_retryable=True,
                is_user_fixable=False,
            )
        yield StreamChunk(text="hello")
        yield StreamChunk(done=True)

    provider = FakeProvider(stream=fail_before_output)
    delays: list[float] = []
    router = _router(provider, delays=delays)

    chunks = list(router.stream("fake", _request()))

    assert [chunk.text for chunk in chunks if chunk.text] == ["hello"]
    assert attempts["count"] == 2
    assert delays == [0.25]


def test_stream_does_not_retry_after_first_chunk():
    attempts = {"count": 0}

    def fail_after_first_chunk(request, *, inactivity_timeout):
        attempts["count"] += 1
        yield StreamChunk(text="partial")
        raise BaseError(
            ErrorCode.INFERENCE_FAILED,
            "mid stream",
            is_retryable=True,
            is_user_fixable=False,
        )

    provider = FakeProvider(stream=fail_after_first_chunk)
    delays: list[float] = []
    router = _router(provider, delays=delays)

    with pytest.raises(BaseError) as exc_info:
        list(router.stream("fake", _request()))

    assert exc_info.value.message == "mid stream"
    assert attempts["count"] == 1
    assert delays == []
