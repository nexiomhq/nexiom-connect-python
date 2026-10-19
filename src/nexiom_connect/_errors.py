from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

__all__ = [
    "ErrorKind",
    "NexiomError",
    "NexiomValidationError",
    "NexiomWebhookVerificationError",
    "ResponseMetadata",
    "WebhookVerificationReason",
]


class ErrorKind(str, enum.Enum):
    """What went wrong with a request that raised `NexiomError`."""

    API = "api"
    """The API answered with an HTTP error status."""

    NETWORK = "network"
    """The request could not reach the API or the connection failed."""

    TIMEOUT = "timeout"
    """The request deadline passed, including retries and waits."""

    PROTOCOL = "protocol"
    """The API answered successfully with a body the SDK cannot read."""

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ResponseMetadata:
    """What the SDK knows about the last HTTP attempt of a failed request."""

    status: int | None = None
    """HTTP status, or `None` when no response was received."""

    headers: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Response headers with lowercase names."""

    request_id: str | None = None
    """Request ID from the response headers or body, for support requests."""

    idempotency_key: str | None = None
    """The send's idempotency key. Reuse it to retry the same email or message safely."""


class NexiomError(Exception):
    """An API or transport failure.

    Does not retain request headers or the underlying transport exception, so the API key
    cannot leak through it.
    """

    def __init__(
        self,
        message: str,
        kind: ErrorKind,
        response: ResponseMetadata | None = None,
        code: str | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)

        self.message = message
        self.kind = kind
        self.response = response if response is not None else ResponseMetadata()

        self.code = code
        """Machine-readable API error code, such as `rate_limited`."""

        self.details = details
        """Additional error details from the API, such as validation failures."""

    @property
    def status(self) -> int | None:
        """HTTP status, or `None` when no response was received."""
        return self.response.status

    @property
    def request_id(self) -> str | None:
        """Request ID from the response headers or body, for support requests."""
        return self.response.request_id

    def __reduce__(self) -> tuple[Any, ...]:
        return (type(self), (self.message, self.kind, self.response, self.code, self.details))

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(kind={self.kind.value!r}, status={self.status!r}, "
            f"code={self.code!r}, message={self.message!r})"
        )


class NexiomValidationError(ValueError):
    """Invalid SDK configuration or arguments; raised before making a request."""


WebhookVerificationReason = Literal[
    "missing_headers",
    "invalid_timestamp",
    "timestamp_out_of_tolerance",
    "invalid_signature",
    "invalid_payload",
]


class NexiomWebhookVerificationError(Exception):
    """A webhook request that is not a genuine, current Nexiom Connect event. Respond with 400."""

    MISSING_HEADERS: ClassVar[WebhookVerificationReason] = "missing_headers"
    INVALID_TIMESTAMP: ClassVar[WebhookVerificationReason] = "invalid_timestamp"
    TIMESTAMP_OUT_OF_TOLERANCE: ClassVar[WebhookVerificationReason] = "timestamp_out_of_tolerance"
    INVALID_SIGNATURE: ClassVar[WebhookVerificationReason] = "invalid_signature"
    INVALID_PAYLOAD: ClassVar[WebhookVerificationReason] = "invalid_payload"

    def __init__(self, message: str, reason: WebhookVerificationReason) -> None:
        super().__init__(message)

        self.message = message

        self.reason: WebhookVerificationReason = reason
        """Which check failed, such as `invalid_signature`."""

    def __reduce__(self) -> tuple[Any, ...]:
        return (type(self), (self.message, self.reason))

    def __repr__(self) -> str:
        return f"{type(self).__name__}(reason={self.reason!r}, message={self.message!r})"
