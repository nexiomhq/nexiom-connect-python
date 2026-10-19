from __future__ import annotations

import asyncio
import datetime as dt
import logging
import pickle
import re
import time
import traceback
from email.utils import format_datetime
from typing import TYPE_CHECKING, Any

import anyio
import httpx
import pytest

from nexiom_connect import (
    AsyncNexiomConnect,
    ErrorKind,
    NexiomConnect,
    NexiomError,
    NexiomWebhookVerificationError,
    __version__,
)

from .conftest import API_KEY, BASE_URL, FakeApi

if TYPE_CHECKING:
    from collections.abc import Callable

RETRY_STATUSES = [408, 429, 500, 502, 503, 504]

EMAIL: dict[str, Any] = {
    "from_": "hello@example.com",
    "to": "customer@example.com",
    "subject": "Welcome",
    "text": "Thanks for joining us.",
}

SENT = {"messageId": "msg_1", "deliveryIds": ["dlv_1"], "totalQueued": 1, "scheduledAt": None}

PAGE = {"items": [], "total": 0, "page": 1, "limit": 50}


def test_requests_carry_authentication_and_identification(api: FakeApi) -> None:
    api.ok(PAGE)

    api.call(lambda nexiom: nexiom.contacts.list())

    call = api.last
    assert call.method == "GET"
    assert call.path == "/api/v1/emails/contacts"
    assert call.headers["authorization"] == f"Bearer {API_KEY}"
    assert call.headers["accept"] == "application/json"
    assert call.headers["user-agent"] == f"nexiom-connect-python/{__version__}"
    assert "content-type" not in call.headers
    assert "idempotency-key" not in call.headers


def test_api_key_is_not_exposed(api: FakeApi, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    api.reply(404, {"error": "not_found", "message": "Contact not found"})

    client = api.client()

    with pytest.raises(NexiomError) as raised:
        api.call(lambda nexiom: nexiom.contacts.get("ct_1"))

    exposed = [
        repr(client),
        str(client),
        repr(vars(client)),
        repr(client._transport),
        repr(vars(client._transport)),
        repr(raised.value),
        str(raised.value),
        repr(vars(raised.value)),
        "".join(traceback.format_exception(raised.value)),
        "".join(
            traceback.TracebackException.from_exception(raised.value, capture_locals=True).format()
        ),
        caplog.text,
    ]

    for text in exposed:
        assert API_KEY not in text

    with pytest.raises(TypeError, match="cannot be pickled"):
        pickle.dumps(client._transport._api_key)


def test_custom_http_client_is_used_and_left_open() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)

        return httpx.Response(302, headers={"location": "https://elsewhere.example.test/"})

    http_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
        headers={"x-trace": "on"},
    )

    with (
        NexiomConnect(API_KEY, base_url=BASE_URL, http_client=http_client) as nexiom,
        pytest.raises(NexiomError) as raised,
    ):
        nexiom.contacts.list()

    assert raised.value.status == 302
    assert len(seen) == 1
    assert seen[0].headers["x-trace"] == "on"
    assert not http_client.is_closed

    owned = NexiomConnect(API_KEY)
    owned.close()
    assert owned._transport._http.is_closed


@pytest.mark.anyio
async def test_custom_async_http_client_is_used_and_left_open() -> None:
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"data": PAGE})),
    )

    async with AsyncNexiomConnect(API_KEY, base_url=BASE_URL, http_client=http_client) as nexiom:
        assert await nexiom.contacts.list() == PAGE

    assert not http_client.is_closed

    owned = AsyncNexiomConnect(API_KEY)
    await owned.close()
    assert owned._transport._http.is_closed

    await http_client.aclose()


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422])
def test_client_errors_are_not_retried(api: FakeApi, status: int) -> None:
    api.reply(
        status,
        {
            "error": "not_found",
            "code": "contact_not_found",
            "message": "Contact not found",
            "details": [{"field": "id"}],
            "correlationId": "req_body",
        },
        headers={"x-request-id": "req_header"},
    )

    with pytest.raises(NexiomError) as raised:
        api.call(lambda nexiom: nexiom.contacts.get("ct_1"), max_retries=5)

    error = raised.value
    assert error.kind is ErrorKind.API
    assert error.status == status
    assert error.code == "contact_not_found"
    assert error.message == str(error) == "Contact not found"
    assert error.request_id == "req_body"
    assert error.details == [{"field": "id"}]
    assert error.response.headers["x-request-id"] == ("req_header",)
    assert len(api.calls) == 1


def test_error_code_falls_back_to_the_error_field(api: FakeApi) -> None:
    api.reply(403, {"error": "not_allowed", "message": "Missing permission"})

    with pytest.raises(NexiomError) as raised:
        api.call(lambda nexiom: nexiom.contacts.delete("ct_1"))

    assert raised.value.code == "not_allowed"


def test_redirects_are_not_followed(api: FakeApi) -> None:
    api.reply(302, {}, headers={"location": "https://attacker.example.test/collect"})

    with pytest.raises(NexiomError) as raised:
        api.call(lambda nexiom: nexiom.contacts.list())

    assert raised.value.kind is ErrorKind.API
    assert raised.value.status == 302
    assert len(api.calls) == 1


def test_non_json_error_keeps_diagnostics(api: FakeApi) -> None:
    api.reply(502, b"<html>Bad gateway</html>", headers={"x-request-id": "req_gateway"})

    with pytest.raises(NexiomError) as raised:
        api.call(lambda nexiom: nexiom.contacts.create(email="a@example.com"))

    error = raised.value
    assert error.kind is ErrorKind.API
    assert error.status == 502
    assert error.request_id == "req_gateway"
    assert error.message == "Request failed with HTTP 502"
    assert error.code is None


@pytest.mark.parametrize(
    "body",
    [b"", b"not json", b"null", b'"text"', b"[]", b"{}", b'{"data": null}', b'{"success": "yes"}'],
)
def test_invalid_success_bodies_are_protocol_errors(api: FakeApi, body: bytes) -> None:
    api.reply(200, body, headers={"x-correlation-id": "req_proto"})

    with pytest.raises(NexiomError) as raised:
        api.call(lambda nexiom: nexiom.contacts.list())

    assert raised.value.kind is ErrorKind.PROTOCOL
    assert raised.value.status == 200
    assert raised.value.request_id == "req_proto"
    assert len(api.calls) == 1


def test_delete_responses_are_returned(api: FakeApi) -> None:
    api.reply(200, {"success": True})

    assert api.call(lambda nexiom: nexiom.contacts.delete("ct_1")) == {"success": True}


def test_errors_survive_pickling(api: FakeApi) -> None:
    api.reply(429, {"code": "rate_limited", "message": "Slow down", "details": {"retry": 1}})

    with pytest.raises(NexiomError) as raised:
        api.call(lambda nexiom: nexiom.contacts.create(email="a@example.com"))

    copy = pickle.loads(pickle.dumps(raised.value))  # noqa: S301 - round-trips our own object.

    assert isinstance(copy, NexiomError)
    assert (copy.message, copy.kind, copy.status, copy.code, copy.details) == (
        "Slow down",
        ErrorKind.API,
        429,
        "rate_limited",
        {"retry": 1},
    )
    assert copy.response == raised.value.response

    refused = NexiomWebhookVerificationError("Bad signature", "invalid_signature")
    assert pickle.loads(pickle.dumps(refused)).reason == "invalid_signature"  # noqa: S301


@pytest.mark.parametrize("status", RETRY_STATUSES)
def test_email_send_retries_with_the_same_key(api: FakeApi, status: int) -> None:
    api.reply(status, {"message": "Try again"})
    api.reply(status, {"message": "Try again"})
    api.ok(SENT, status=202)

    result = api.call(lambda nexiom: nexiom.emails.send(**EMAIL))

    assert result == SENT
    assert len(api.calls) == 3
    keys = {call.headers["idempotency-key"] for call in api.calls}
    assert len(keys) == 1
    assert re.fullmatch(r"[0-9a-f]{32}", keys.pop())
    assert len({call.content for call in api.calls}) == 1
    assert len(api.sleeps) == 2


def test_reads_retry_a_bounded_number_of_times(api: FakeApi) -> None:
    for _ in range(3):
        api.reply(503, {"message": "Unavailable"})

    with pytest.raises(NexiomError) as raised:
        api.call(lambda nexiom: nexiom.contacts.list(), max_retries=2)

    assert raised.value.status == 503
    assert len(api.calls) == 3

    # Exponential backoff with jitter: 0.5 s, then 1 s, each scaled by 0.75 to 1.
    first, second = api.sleeps
    assert 0.375 <= first <= 0.5
    assert 0.75 <= second <= 1.0


def test_retries_can_be_turned_off(api: FakeApi) -> None:
    api.reply(503, {"message": "Unavailable"})

    with pytest.raises(NexiomError):
        api.call(lambda nexiom: nexiom.contacts.list(), max_retries=0)

    assert len(api.calls) == 1


@pytest.mark.parametrize(
    "operation",
    [
        lambda nexiom: nexiom.contacts.create(email="a@example.com"),
        lambda nexiom: nexiom.contacts.update("ct_1", email="a@example.com"),
        lambda nexiom: nexiom.contacts.delete("ct_1"),
        lambda nexiom: nexiom.contacts.properties.create(name="plan", type="string"),
        lambda nexiom: nexiom.contacts.properties.update("prop_1", name="tier"),
        lambda nexiom: nexiom.contacts.properties.delete("prop_1"),
        lambda nexiom: nexiom.emails.reschedule("msg_1", scheduled_at="2026-10-20T09:00:00Z"),
        lambda nexiom: nexiom.domains.create(domain="mail.example.com"),
        lambda nexiom: nexiom.domains.delete("dom_1"),
    ],
)
def test_mutations_never_retry(api: FakeApi, operation: Callable[[Any], Any]) -> None:
    api.reply(503, {"message": "Unavailable"})

    with pytest.raises(NexiomError):
        api.call(operation, max_retries=5)

    assert len(api.calls) == 1
    assert api.sleeps == []


def test_network_failure_is_redacted(api: FakeApi) -> None:
    for _ in range(3):
        api.fail(httpx.ConnectError("connection refused"))

    with pytest.raises(NexiomError) as raised:
        api.call(lambda nexiom: nexiom.contacts.list())

    error = raised.value
    assert error.kind is ErrorKind.NETWORK
    assert error.message == "Unable to complete the API request"
    assert error.status is None
    assert error.__cause__ is None
    assert error.__context__ is None
    assert len(api.calls) == 3


def test_network_failure_clears_stale_metadata(api: FakeApi) -> None:
    api.reply(503, {"message": "Unavailable"}, headers={"x-request-id": "req_old"})
    api.fail(httpx.ReadError("reset"))

    with pytest.raises(NexiomError) as raised:
        api.call(lambda nexiom: nexiom.contacts.list(), max_retries=1)

    error = raised.value
    assert error.kind is ErrorKind.NETWORK
    assert error.status is None
    assert error.request_id is None
    assert error.response.headers == {}


def test_transport_timeouts_are_timeouts(api: FakeApi) -> None:
    api.fail(httpx.ReadTimeout("timed out"))

    with pytest.raises(NexiomError) as raised:
        api.call(
            lambda nexiom: nexiom.emails.send(**EMAIL, idempotency_key="order-1"), max_retries=0
        )

    assert raised.value.kind is ErrorKind.TIMEOUT
    assert raised.value.response.idempotency_key == "order-1"
    assert raised.value.__context__ is None


@pytest.mark.parametrize(
    "retry_after",
    [
        "60",
        format_datetime(dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5), usegmt=True),
    ],
)
def test_retry_after_beyond_the_deadline_fails_fast(api: FakeApi, retry_after: str) -> None:
    api.reply(
        429, {"code": "rate_limited", "message": "Slow down"}, headers={"retry-after": retry_after}
    )

    with pytest.raises(NexiomError) as raised:
        api.call(lambda nexiom: nexiom.contacts.list(), timeout=5)

    assert raised.value.kind is ErrorKind.API
    assert raised.value.status == 429
    assert len(api.calls) == 1
    assert api.sleeps == []


def test_retry_after_within_the_deadline_is_honored(api: FakeApi) -> None:
    api.reply(503, {"message": "Unavailable"}, headers={"retry-after": "1.5"})
    api.reply(
        429,
        {"message": "Slow down"},
        headers={
            "retry-after": format_datetime(
                dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=3),
                usegmt=True,
            ),
        },
    )
    api.reply(503, {"message": "Unavailable"}, headers={"retry-after": "not a date"})
    api.ok(PAGE)

    assert api.call(lambda nexiom: nexiom.contacts.list(), max_retries=3) == PAGE

    seconds, date, fallback = api.sleeps
    assert seconds == 1.5
    assert 1.0 <= date <= 3.0
    assert 0.75 <= fallback <= 2.0


def test_per_request_overrides(api: FakeApi) -> None:
    api.reply(503, {"message": "Unavailable"})
    api.reply(503, {"message": "Unavailable"})
    api.ok(PAGE)

    assert api.call(lambda nexiom: nexiom.contacts.list(max_retries=2), max_retries=0) == PAGE
    assert len(api.calls) == 3

    api.ok(PAGE)
    api.call(lambda nexiom: nexiom.contacts.list(timeout=7), timeout=60)
    assert 6.5 < api.last.timeout["read"] <= 7  # type: ignore[operator]

    def slow(_: httpx.Request) -> httpx.Response:
        time.sleep(0.05)

        return httpx.Response(200, json={"data": PAGE})

    api.responses.append(slow)

    with pytest.raises(NexiomError) as raised:
        api.call(lambda nexiom: nexiom.contacts.list(timeout=0.01))

    assert raised.value.kind is ErrorKind.TIMEOUT


class _HangingTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.attempts = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.attempts += 1
        await anyio.sleep(10)

        return httpx.Response(200, json={"data": PAGE})


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio", "trio"])
async def test_async_cancellation_propagates(anyio_backend: str) -> None:
    transport = _HangingTransport()
    nexiom = AsyncNexiomConnect(
        API_KEY,
        base_url=BASE_URL,
        http_client=httpx.AsyncClient(transport=transport),
    )

    with anyio.move_on_after(0.05) as scope:
        await nexiom.contacts.list()

    assert scope.cancelled_caught
    assert transport.attempts == 1

    if anyio_backend == "asyncio":
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(nexiom.contacts.list(), 0.05)

        assert transport.attempts == 2

    await nexiom.close()


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["trio"])
async def test_async_client_runs_on_trio(anyio_backend: str) -> None:
    replies = iter(
        [
            httpx.Response(503, json={"message": "Unavailable"}, headers={"retry-after": "0.01"}),
            httpx.Response(200, json={"data": PAGE}),
        ],
    )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: next(replies)))

    async with AsyncNexiomConnect(API_KEY, base_url=BASE_URL, http_client=http_client) as nexiom:
        assert await nexiom.contacts.list() == PAGE
