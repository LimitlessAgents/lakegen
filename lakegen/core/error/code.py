from enum import Enum


class ErrorCode(str, Enum):
    """Stable, machine-readable error identifiers.

    Subclasses ``str`` so a code serializes as its plain value in JSON payloads.
    The set is intentionally scoped to lakegen's real failure modes (agent
    input, resource state, catalog connectivity/auth, credential storage) rather
    than a generic status taxonomy.
    """

    # Invalid input from the caller/agent.
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    INVALID_TYPE = "INVALID_TYPE"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"

    # Resource state.
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"

    # Auth when reaching an external catalog or its storage.
    UNAUTHENTICATED = "UNAUTHENTICATED"
    PERMISSION_DENIED = "PERMISSION_DENIED"

    # Connecting to an external catalog.
    CONNECTION_FAILED = "CONNECTION_FAILED"
    CONNECTION_TIMEOUT = "CONNECTION_TIMEOUT"

    # A dependency or backend was unavailable.
    UNAVAILABLE = "UNAVAILABLE"

    # Retained for API compatibility with earlier credential storage errors.
    KEYRING = "KEYRING"
    JSON = "JSON"

    # Inference / LLM provider failures.
    INFERENCE_FAILED = "INFERENCE_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"

    # Catch-all for unexpected/unclassified failures.
    INTERNAL = "INTERNAL"
