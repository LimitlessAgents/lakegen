from lakegen.inference.model import ChatRequest, ChatResponse
from lakegen.inference.registry import registry as inference_registry


class Router:
    def complete(self, provider: str, request: ChatRequest) -> ChatResponse:
        resolved_provider = inference_registry.get(provider) or None
        if not resolved_provider:
            raise Exception(
                f"Inference provider {provider!r} doesn't exist."
            )
        response = resolved_provider.complete(request)
        return response


router = Router()