"""Verify webhook requests. Makes no network request."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, ClassVar, Final, TypeAlias, cast

from .. import _validate as validate
from .._errors import NexiomValidationError, NexiomWebhookVerificationError

if TYPE_CHECKING:
    from ..types import WebhookEvent

WebhookPayload: TypeAlias = str | bytes | bytearray | memoryview
"""The raw request body, exactly as received."""

_HeaderValue: TypeAlias = str | bytes | Sequence[str] | Sequence[bytes] | None

WebhookHeaders: TypeAlias = (
    Mapping[str, _HeaderValue]
    | Mapping[bytes, _HeaderValue]
    | Iterable[tuple[str, str]]
    | Iterable[tuple[bytes, bytes]]
)
"""Request headers: Django's `request.headers`, Flask's or Starlette's `request.headers`, a `dict`,
or a list of `(name, value)` pairs such as ASGI's `scope["headers"]`."""

# Unix seconds; 16 digits reaches past the year 300,000,000 and keeps the value comparable.
_TIMESTAMP: Final = re.compile(r"[0-9]{1,16}", re.ASCII)

_SIGNATURE: Final = re.compile(r"[0-9a-fA-F]{64}", re.ASCII)


class Webhooks:
    """Verify webhook requests. Makes no network request and needs no API key."""

    TIMESTAMP_HEADER: ClassVar[str] = "x-nexiom-timestamp"
    SIGNATURE_HEADER: ClassVar[str] = "x-nexiom-signature"

    def construct_event(
        self,
        payload: WebhookPayload,
        headers: WebhookHeaders,
        secret: str,
        *,
        tolerance: int = 300,
    ) -> WebhookEvent:
        """Checks a webhook request's signature and timestamp, then returns its event.

        Pass the raw body exactly as received (`request.body` in Django, `request.get_data()` in
        Flask, `await request.body()` in FastAPI and Starlette), the request headers, and the
        endpoint's signing secret (`whsec_…`). JSON that was parsed and encoded again does not
        match the signature.

        Raises `NexiomWebhookVerificationError` when the request is not genuine or not current;
        respond with 400. Raises `NexiomValidationError` when an argument is invalid.
        """
        validate.non_empty(secret, "secret")
        validate.integer(tolerance, "tolerance", 1)
        body = _body(payload)

        timestamp = _header(headers, self.TIMESTAMP_HEADER)
        signature = _header(headers, self.SIGNATURE_HEADER)

        if timestamp is None or signature is None:
            raise NexiomWebhookVerificationError(
                f"Missing {self.TIMESTAMP_HEADER} or {self.SIGNATURE_HEADER} header",
                NexiomWebhookVerificationError.MISSING_HEADERS,
            )

        if _TIMESTAMP.fullmatch(timestamp) is None:
            raise NexiomWebhookVerificationError(
                f"{self.TIMESTAMP_HEADER} must be a Unix time in seconds",
                NexiomWebhookVerificationError.INVALID_TIMESTAMP,
            )

        if abs(int(time.time()) - int(timestamp)) > tolerance:
            raise NexiomWebhookVerificationError(
                "The webhook timestamp is outside the allowed tolerance",
                NexiomWebhookVerificationError.TIMESTAMP_OUT_OF_TOLERANCE,
            )

        expected = hmac.new(
            secret.encode("utf-8"),
            timestamp.encode("ascii") + b"." + body,
            hashlib.sha256,
        ).hexdigest()

        if _SIGNATURE.fullmatch(signature) is None or not hmac.compare_digest(
            expected, signature.lower()
        ):
            raise NexiomWebhookVerificationError(
                "The webhook signature does not match the payload and secret",
                NexiomWebhookVerificationError.INVALID_SIGNATURE,
            )

        return _event(body)


def _body(payload: object) -> bytes:
    if isinstance(payload, str):
        try:
            return payload.encode("utf-8")
        except UnicodeEncodeError:
            # A lone surrogate cannot come from a request body, so this text is not the body.
            raise NexiomWebhookVerificationError(
                "The webhook signature does not match the payload and secret",
                NexiomWebhookVerificationError.INVALID_SIGNATURE,
            ) from None

    if isinstance(payload, (bytes, bytearray, memoryview)):
        return bytes(payload)

    raise NexiomValidationError(
        "payload must be the raw request body as str or bytes, not parsed JSON",
    )


def _header(headers: object, name: str) -> str | None:
    """The first value of a header, matched case-insensitively, or `None` when absent or blank."""
    items = getattr(headers, "items", None)
    pairs = items() if callable(items) else headers

    if not isinstance(pairs, Iterable):
        raise NexiomValidationError("headers must be a mapping or a list of (name, value) pairs")

    for pair in pairs:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise NexiomValidationError(
                "headers must be a mapping or a list of (name, value) pairs"
            )

        key, value = pair

        if _text(key).lower() != name:
            continue

        if isinstance(value, (list, tuple)):
            value = value[0] if value else None

        first = _text(value).strip() if isinstance(value, (str, bytes)) else ""

        return first or None

    return None


def _text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("latin-1")

    return value if isinstance(value, str) else ""


def _event(body: bytes) -> WebhookEvent:
    try:
        decoded: Any = json.loads(body.decode("utf-8"))
    except ValueError:
        decoded = None

    if (
        not isinstance(decoded, dict)
        or not isinstance(decoded.get("id"), str)
        or not isinstance(decoded.get("type"), str)
        or not isinstance(decoded.get("schema_version"), int)
        or isinstance(decoded.get("schema_version"), bool)
        or not isinstance(decoded.get("data"), dict)
        or not isinstance(decoded.get("created_at"), str)
    ):
        raise NexiomWebhookVerificationError(
            "The webhook payload is not an event envelope",
            NexiomWebhookVerificationError.INVALID_PAYLOAD,
        )

    return cast("WebhookEvent", decoded)
