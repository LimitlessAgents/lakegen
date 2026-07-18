from lakegen.inference.protocol import InferenceProvider


class InferenceRegistry:
    """Looks up providers by name."""

    def __init__(self) -> None:
        self._providers: dict[str, InferenceProvider] = {}

    def get(self, name: str) -> InferenceProvider | None:
        return self._providers.get(name)

    def register(self, provider: InferenceProvider) -> None:
        self._providers[provider.name] = provider


registry = InferenceRegistry()
