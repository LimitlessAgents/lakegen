"""Configuration defaults and environment overrides for LakeGen."""

import os
from dataclasses import dataclass

ENV_OPENAI_MODEL = "OPENAI_MODEL"
ENV_OPENAI_BASE_URL = "OPENAI_BASE_URL"


@dataclass(frozen=True)
class EnvConfig:
    """Immutable inference settings resolved from the environment.

    Field defaults are the built-in fallbacks; :meth:`from_env` layers the
    ``OPENAI_*`` variables on top in a single place. ``provider`` is carried now
    so a future provider override has a home without new ``get_default_*``
    helpers. Like :class:`lakegen.session.environment.Environment`, callers pass
    one concrete object (and tests inject one) instead of reading env scattered
    across the stack.
    """

    base_url: str | None = None
    model: str = "gpt-4o-mini"
    provider: str = "openai"

    @classmethod
    def default(cls) -> "EnvConfig":
        """Return the built-in fallbacks, ignoring the environment."""
        return cls()

    @classmethod
    def from_env(cls) -> "EnvConfig":
        """Read every setting from the environment in one place.

        Unset variables fall back to the field defaults above.
        """
        defaults = cls.default()
        return cls(
            base_url=os.environ.get(ENV_OPENAI_BASE_URL, defaults.base_url),
            model=os.environ.get(ENV_OPENAI_MODEL, defaults.model),
            provider=defaults.provider,
        )
