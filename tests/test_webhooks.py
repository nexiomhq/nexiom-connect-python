from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import pytest

from nexiom_connect import (
    AsyncNexiomConnect,
    NexiomConnect,
    NexiomValidationError,
    NexiomWebhookVerificationError,
    Webhooks,
)

from .conftest import API_KEY

SECRET = "whsec_test_signing_secret"

EVENT: dict[str, Any] = {
    "id": "00000000-0000-4000-8000-000000000001",
    "type": "email.bounced",
    "schema_version": 1,
    "data": {
        "id": "dlv_1",
        "message_id": "msg_1",
        "recipient": "ada@example.com",
        "occurred_at": "2026-10-14T09:30:00.000Z",
    },
    "created_at": "2026-10-14T09:30:01.000Z",
}

BODY = json.dumps(EVENT, indent=2).encode()


def sign(body: bytes, timestamp: int | str | None = None, secret: str = SECRET) -> dict[str, str]:
    stamp = str(int(time.time()) if timestamp is None else timestamp)
    signature = hmac.new(secret.encode(), stamp.encode() + b"." + body, hashlib.sha256).hexdigest()

    return {"x-nexiom-timestamp": stamp, "x-nexiom-signature": signature}


def verify(payload: Any, headers: Any, secret: Any = SECRET, **options: Any) -> Any:
    return Webhooks().construct_event(payload, headers, secret, **options)


def reason(payload: Any, headers: Any, secret: str = SECRET, **options: Any) -> str:
    with pytest.raises(NexiomWebhookVerificationError) as raised:
        verify(payload, headers, secret, **options)

    return raised.value.reason


def test_signed_requests_return_their_event() -> None:
    headers = sign(BODY)

    for payload in (BODY, BODY.decode(), bytearray(BODY), memoryview(BODY)):
        assert verify(payload, headers) == EVENT

    future = {**EVENT, "type": "invoice.paid", "data": {"anything": True}}
    body = json.dumps(future).encode()
    assert verify(body, sign(body)) == future

    unicode = {**EVENT, "data": {**EVENT["data"], "recipient": "أمينة@example.com"}}
    body = json.dumps(unicode, ensure_ascii=False).encode()
    assert verify(body.decode(), sign(body))["data"]["recipient"] == "أمينة@example.com"


def test_webhooks_work_without_a_client() -> None:
    assert Webhooks().construct_event(BODY, sign(BODY), SECRET) == EVENT
    assert NexiomConnect(API_KEY).webhooks.construct_event(BODY, sign(BODY), SECRET) == EVENT
    assert AsyncNexiomConnect(API_KEY).webhooks.construct_event(BODY, sign(BODY), SECRET) == EVENT


def test_missing_or_malformed_headers_are_refused() -> None:
    headers = sign(BODY)

    assert reason(BODY, {}) == "missing_headers"
    assert reason(BODY, {"x-nexiom-signature": headers["x-nexiom-signature"]}) == "missing_headers"
    assert reason(BODY, {"x-nexiom-timestamp": headers["x-nexiom-timestamp"]}) == "missing_headers"
    assert reason(BODY, {**headers, "x-nexiom-signature": "  "}) == "missing_headers"
    assert reason(BODY, {**headers, "x-nexiom-timestamp": []}) == "missing_headers"

    for stamp in ("1.5", "-1", "now", "1e9", "1" * 17, "١٧٠٠"):
        assert reason(BODY, {**headers, "x-nexiom-timestamp": stamp}) == "invalid_timestamp"


def test_timestamps_outside_the_tolerance_are_refused() -> None:
    now = int(time.time())

    assert reason(BODY, sign(BODY, now - 301)) == "timestamp_out_of_tolerance"
    assert reason(BODY, sign(BODY, now + 301)) == "timestamp_out_of_tolerance"
    assert reason(BODY, sign(BODY, 0)) == "timestamp_out_of_tolerance"

    assert verify(BODY, sign(BODY, now - 250)) == EVENT
    assert verify(BODY, sign(BODY, now - 3000), tolerance=3600) == EVENT
    assert reason(BODY, sign(BODY, now - 30), tolerance=10) == "timestamp_out_of_tolerance"


def test_changed_requests_are_refused() -> None:
    headers = sign(BODY)

    assert reason(BODY + b" ", headers) == "invalid_signature"
    assert reason(json.dumps(EVENT).encode(), headers) == "invalid_signature"
    assert reason(BODY, headers, secret="whsec_another_secret") == "invalid_signature"
    assert reason(BODY, headers, secret=SECRET.removeprefix("whsec_")) == "invalid_signature"
    assert reason(BODY, headers, secret=API_KEY) == "invalid_signature"

    stamp = int(headers["x-nexiom-timestamp"])
    assert reason(BODY, {**headers, "x-nexiom-timestamp": str(stamp - 1)}) == "invalid_signature"

    signature = headers["x-nexiom-signature"]
    flipped = ("0" if signature[0] != "0" else "1") + signature[1:]
    assert reason(BODY, {**headers, "x-nexiom-signature": flipped}) == "invalid_signature"
    assert reason(BODY, {**headers, "x-nexiom-signature": signature[:-2]}) == "invalid_signature"
    assert reason(BODY, {**headers, "x-nexiom-signature": f"v1={signature}"}) == "invalid_signature"
    assert verify(BODY, {**headers, "x-nexiom-signature": signature.upper()}) == EVENT

    assert reason("\ud800", sign(b"x")) == "invalid_signature"


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"\xff\xfe{}",
        b"[]",
        b'"event"',
        json.dumps({**EVENT, "id": 1}).encode(),
        json.dumps({**EVENT, "type": None}).encode(),
        json.dumps({**EVENT, "schema_version": "1"}).encode(),
        json.dumps({**EVENT, "schema_version": True}).encode(),
        json.dumps({**EVENT, "data": []}).encode(),
        json.dumps({key: value for key, value in EVENT.items() if key != "created_at"}).encode(),
    ],
)
def test_signed_bodies_that_are_not_events_are_refused(body: bytes) -> None:
    assert reason(body, sign(body)) == "invalid_payload"


class _CaseInsensitiveHeaders:
    """Like Django's request.headers and Flask's EnvironHeaders: items() with any casing."""

    def __init__(self, pairs: list[tuple[str, str]]) -> None:
        self._pairs = pairs

    def items(self) -> list[tuple[str, str]]:
        return self._pairs


def test_headers_are_read_from_every_framework_shape() -> None:
    headers = sign(BODY)
    stamp, signature = headers["x-nexiom-timestamp"], headers["x-nexiom-signature"]

    shapes: list[Any] = [
        {"X-Nexiom-Timestamp": stamp, "X-NEXIOM-SIGNATURE": signature},
        {"x-nexiom-timestamp": [stamp, "0"], "x-nexiom-signature": (signature,)},
        [("X-Nexiom-Timestamp", stamp), ("X-Nexiom-Signature", signature)],
        [(b"x-nexiom-timestamp", stamp.encode()), (b"x-nexiom-signature", signature.encode())],
        {b"x-nexiom-timestamp": stamp.encode(), b"x-nexiom-signature": [signature.encode()]},
        {"x-nexiom-timestamp": f" {stamp} ", "x-nexiom-signature": f"{signature}\t"},
        _CaseInsensitiveHeaders([("X-Nexiom-Timestamp", stamp), ("X-Nexiom-Signature", signature)]),
    ]

    for shape in shapes:
        assert verify(BODY, shape) == EVENT


def test_invalid_arguments_are_programming_errors() -> None:
    headers = sign(BODY)

    for secret in ("", "   ", None):
        with pytest.raises(NexiomValidationError, match="secret"):
            verify(BODY, headers, secret=secret)

    for tolerance in (0, -5, True, 1.5):
        with pytest.raises(NexiomValidationError, match="tolerance"):
            verify(BODY, headers, tolerance=tolerance)

    for payload in (EVENT, None, 5):
        with pytest.raises(NexiomValidationError, match="raw request body"):
            verify(payload, headers)

    for bad_headers in (None, 5, [("only-one",)]):
        with pytest.raises(NexiomValidationError, match="headers"):
            verify(BODY, bad_headers)


def test_refusals_say_why() -> None:
    with pytest.raises(NexiomWebhookVerificationError) as raised:
        verify(BODY, {})

    error = raised.value
    assert error.reason == NexiomWebhookVerificationError.MISSING_HEADERS
    assert "x-nexiom-timestamp" in str(error)
    assert "missing_headers" in repr(error)
