from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InferencePolicy:
    """Immutable timeout and retry settings shared by a Router.

    The Router owns one policy for all calls. Attempt counters and backoff
    delays stay local to each ``complete`` / ``stream`` invocation so concurrent
    callers cannot interfere with each other.
    """

    inactivity_timeout: float = 60.0
    """Seconds of network silence before a provider call fails.

    This is an inactivity / per-operation timeout, not a hard wall-clock
    deadline for the whole response. A long but healthy stream can keep going;
    a stalled connection fails.
    """

    max_attempts: int = 3
    """Total tries for one request, including the first attempt."""

    backoff_base: float = 0.5
    """Initial delay in seconds before the first retry."""

    backoff_cap: float = 8.0
    """Upper bound on exponential backoff delay, in seconds."""

    jitter: bool = True
    """When true, multiply each delay by a random factor in ``[0, 1]``.

    Full jitter spreads concurrent retries so they do not all hit the
    provider at the same moment.
    """
