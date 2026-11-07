from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ContextPolicy:
    """One budget for everything the model receives.

    ``input_budget`` is the model window minus the space reserved for the
    completion. System prompt, tool definitions, history and the current turn
    all count against it.
    """

    window: int = 200_000
    reserve_ratio: float = 0.10
    history_ratio: float = 0.60
    turn_ratio: float = 0.20
    growth_ratio: float = 0.05
    max_turn_compressions: int = 3

    @property
    def input_budget(self) -> int:
        return int(self.window * (1 - self.reserve_ratio))

    @property
    def history_limit(self) -> int:
        return int(self.input_budget * self.history_ratio)

    @property
    def turn_limit(self) -> int:
        return int(self.input_budget * self.turn_ratio)

    @property
    def growth_limit(self) -> int:
        return int(self.input_budget * self.growth_ratio)

    @classmethod
    def from_env(cls) -> ContextPolicy:
        window = os.getenv("LAKEGEN_CONTEXT_WINDOW")
        reserve_ratio = os.getenv("LAKEGEN_CONTEXT_RESERVE_RATIO")
        return cls(
            window=int(window) if window else cls.window,
            reserve_ratio=float(reserve_ratio) if reserve_ratio else cls.reserve_ratio,
        )


@dataclass
class TurnCompressionState:
    """Hysteresis for current-turn compression.

    Prevents re-summarizing the same turn every iteration and bounds the
    number of compression calls per turn.
    """

    count: int = 0
    tokens: int | None = None

    def needs(self, tokens: int, policy: ContextPolicy) -> bool:
        if tokens < policy.turn_limit:
            return False
        if self.count >= policy.max_turn_compressions:
            return False
        if self.tokens is None:
            return True
        return tokens - self.tokens >= policy.growth_limit

    def record(self, tokens: int) -> None:
        self.count += 1
        self.tokens = tokens
