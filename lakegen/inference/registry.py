from lakegen.inference.protocol import InferenceProvider


class InferenceRegistry:
    """In-memory map of provider name → provider instance."""

    def __init__(self) -> None:
        self._providers: dict[str, InferenceProvider] = {}

    def get(self, name: str) -> InferenceProvider | None:
        """Return the provider registered under ``name``, or ``None``."""
        return self._providers.get(name)

    def register(self, provider: InferenceProvider) -> None:
        """Register ``provider`` under ``provider.name``, replacing any prior entry."""
        self._providers[provider.name] = provider


registry = InferenceRegistry()

