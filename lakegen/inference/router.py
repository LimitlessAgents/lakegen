from collections.abc import Iterator

from lakegen.inference.model import ChatRequest, ChatResponse, StreamChunk
from lakegen.inference.registry import registry as inference_registry


class Router:
    def complete(self, provider: str, request: ChatRequest) -> ChatResponse:
        resolved_provider = inference_registry.get(provider)
        if not resolved_provider:
            raise Exception(
                f"Inference provider {provider!r} doesn't exist."
            )
        return resolved_provider.complete(request)

    def stream(self, provider: str, request: ChatRequest) -> Iterator[StreamChunk]:
        resolved_provider = inference_registry.get(provider)
        if not resolved_provider:
            raise Exception(
                f"Inference provider {provider!r} doesn't exist."
            )
        return resolved_provider.stream(request)


router = Router()