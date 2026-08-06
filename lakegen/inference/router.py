import random as random_module
import time
from collections.abc import Callable, Iterator

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode
from lakegen.inference.model import ChatRequest, ChatResponse, StreamChunk
from lakegen.inference.policy import InferencePolicy
from lakegen.inference.registry import (
    InferenceRegistry,
    registry as inference_registry,
)


class Router:
    """Routes inference calls to providers and applies bounded retries.

    Retry state (attempt count, delay) lives in local variables inside each
    method call. The shared policy and injectable ``sleep`` / ``random``
    callables hold no per-request counters, so concurrent callers on the same
    Router instance do not interfere.

    ``sleep`` and ``random`` default to ``time.sleep`` and ``random.random``.
    Tests can inject fakes to assert backoff without waiting.
    """

    def __init__(
        self,
        policy: InferencePolicy | None = None,
        *,
        registry: InferenceRegistry = inference_registry,
        sleep: Callable[[float], None] = time.sleep,
        random: Callable[[], float] = random_module.random,
    ) -> None:
        self.policy = policy if policy is not None else InferencePolicy()
        self._registry = registry
        self._sleep = sleep
        self._random = random

    def complete(
        self,
        provider: str,
        request: ChatRequest,
    ) -> ChatResponse:
        """Complete a chat request with bounded retry on transient failures.

        Retries only when the error is retryable and not user-fixable.
        Unexpected non-``BaseError`` exceptions are wrapped once as
        ``INFERENCE_FAILED`` and not retried.
        """
        resolved_provider = self._resolve(provider)

        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                return resolved_provider.complete(
                    request,
                    inactivity_timeout=self.policy.inactivity_timeout,
                )
            except BaseError as error:
                if not self._should_retry(error, attempt):
                    raise
                self._backoff(attempt, error)
            except Exception as error:
                # Catch unexpected/unhandled errors and expose a structured BaseError.
                raise BaseError(
                    ErrorCode.INFERENCE_FAILED,
                    f"Inference provider {provider!r} failed.",
                    is_retryable=False,
                    is_user_fixable=False,
                    details={"provider": provider},
                ) from error

        raise RuntimeError("unreachable")

    def stream(self, provider: str, request: ChatRequest) -> Iterator[StreamChunk]:
        """Stream a chat request with retry only before the first chunk.

        Failures while establishing the stream (or before any ``StreamChunk``
        is yielded) use the same bounded backoff as ``complete``.

        Once any chunk has been yielded to the caller, failures are terminal.
        Restarting would replay earlier text/tool events and can duplicate
        side effects. Mid-stream timeouts and connection drops are therefore
        structured ``BaseError`` values but are not retried.
        """
        resolved_provider = self._resolve(provider)

        for attempt in range(1, self.policy.max_attempts + 1):
            yielded = False
            try:
                for chunk in resolved_provider.stream(
                    request,
                    inactivity_timeout=self.policy.inactivity_timeout,
                ):
                    yielded = True
                    yield chunk
                return
            except BaseError as error:
                if yielded or not self._should_retry(error, attempt):
                    raise
                self._backoff(attempt, error)
            except Exception as error:
                # Catch unexpected errors and expose a structured BaseError.
                raise BaseError(
                    ErrorCode.INFERENCE_FAILED,
                    f"Inference provider {provider!r} failed.",
                    is_retryable=False,
                    is_user_fixable=False,
                    details={"provider": provider},
                ) from error

    def _resolve(self, provider: str):
        """Look up a provider by name or raise a user-fixable NOT_FOUND."""
        resolved_provider = self._registry.get(provider)
        if resolved_provider is None:
            raise BaseError(
                ErrorCode.NOT_FOUND,
                f"Inference provider {provider!r} doesn't exist.",
                is_retryable=False,
                is_user_fixable=True,
                details={"provider": provider},
            )
        return resolved_provider

    def _should_retry(self, error: BaseError, attempt: int) -> bool:
        """Return whether another attempt is allowed for this error."""
        return (
            error.is_retryable
            and not error.is_user_fixable
            and attempt < self.policy.max_attempts
        )

    def _backoff(self, attempt: int, error: BaseError) -> None:
        """Sleep before the next attempt.

        Prefer a numeric ``retry_after`` from the error details when present
        (e.g. from an HTTP ``Retry-After`` header), capped by ``backoff_cap``.
        Otherwise use capped exponential delay, optionally with full jitter.
        """
        retry_after = error.details.get("retry_after")
        if isinstance(retry_after, (int, float)) and retry_after >= 0:
            delay = float(retry_after)
        else:
            delay = min(
                self.policy.backoff_base * (2 ** (attempt - 1)),
                self.policy.backoff_cap,
            )
            if self.policy.jitter:
                delay *= self._random()
        self._sleep(delay)


router = Router()
