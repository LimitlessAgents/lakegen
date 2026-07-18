from lakegen.inference.model import ChatRequest, ChatResponse


class Router:
    def complete(provider: str, request: ChatRequest) -> CbatResponse:
        pass