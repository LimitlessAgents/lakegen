from dataclasses import dataclass
from typing import Iterator, Protocol, runtime_checkable

from lakegen.inference.model import ChatRequest, ChatResponse, StreamChunk


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Feature flags describing what a provider can do."""

    chat: bool = True
    tools: bool = False
    streaming: bool = False
    json_schema: bool = False


@runtime_checkable
class InferenceProvider(Protocol):
    """Contract every inference provider must satisfy.

    Providers map vendor-specific SDK failures into ``BaseError`` and honor
    ``inactivity_timeout``. The Router owns retry / backoff decisions; providers
    only enforce the timeout and normalize errors.
    """

    @property
    def name(self) -> str:
        """Stable registry key, e.g. ``\"openai\"``."""
        ...

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Declared feature support for this provider."""
        ...

    def complete(
        self,
        request: ChatRequest,
        *,
        inactivity_timeout: float,
    ) -> ChatResponse:
        """Run a non-streaming completion.

        ``inactivity_timeout`` is keyword-only so callers pass it by name.
        Providers should treat it as network inactivity, not a total deadline.
        """
        ...

    def stream(
        self,
        request: ChatRequest,
        *,
        inactivity_timeout: float,
    ) -> Iterator[StreamChunk]:
        """Yield streaming chunks until the response completes.

        Failures raised before the first chunk may be retried by the Router.
        Failures after any chunk has been yielded are terminal.
        """
        ...
