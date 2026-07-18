from dataclasses import dataclass
from typing import Iterator, Protocol, runtime_checkable

from lakegen.inference.model import ChatRequest, ChatResponse


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """What a provider can do."""

    chat: bool = True
    tools: bool = False
    streaming: bool = False
    json_schema: bool = False


@runtime_checkable
class InferenceProvider(Protocol):
    """Shared shape every provider must match."""

    @property
    def name(self) -> str: ...

    @property
    def capabilities(self) -> ProviderCapabilities: ...

    def complete(self, request: ChatRequest) -> ChatResponse: ...

    def stream(self, request: ChatRequest) -> Iterator: ...
