"""A recording fake API shared by the sync and async clients.

Every test that takes the `api` fixture runs twice: once with `NexiomConnect` and once with
`AsyncNexiomConnect`, through the same `api.call(...)` helper.
"""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

import anyio
import httpx
import pytest

from nexiom_connect import AsyncNexiomConnect, NexiomConnect
from nexiom_connect import _transport as transport

API_KEY = "nc_test_secret_key"

BASE_URL = "https://api.example.test/api"

Mode = Literal["sync", "async"]


@dataclass
class RecordedCall:
    method: str
    path: str
    query: dict[str, str]
    headers: httpx.Headers
    content: bytes
    timeout: dict[str, float | None]

    @property
    def json(self) -> Any:
        return json.loads(self.content) if self.content else None


@dataclass
class FakeApi:
    """Queues responses and records every request the SDK sends."""

    mode: Mode
    responses: deque[httpx.Response | Exception | Callable[[httpx.Request], httpx.Response]] = (
        field(
            default_factory=deque,
        )
    )
    calls: list[RecordedCall] = field(default_factory=list)
    sleeps: list[float] = field(default_factory=list)

    def reply(
        self, status: int = 200, body: Any = None, *, headers: dict[str, str] | None = None
    ) -> None:
        """Queues a JSON response; `body` may be raw bytes for malformed responses."""
        content = body if isinstance(body, bytes) else json.dumps(body).encode()

        self.responses.append(httpx.Response(status, content=content, headers=headers))

    def ok(self, data: Any, *, status: int = 200) -> None:
        self.reply(status, {"message": "Done", "data": data})

    def fail(self, error: Exception) -> None:
        self.responses.append(error)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(
            RecordedCall(
                method=request.method,
                path=request.url.raw_path.split(b"?")[0].decode("ascii"),
                query=dict(request.url.params),
                headers=request.headers,
                content=request.read(),
                timeout=request.extensions.get("timeout", {}),
            ),
        )

        if not self.responses:
            raise AssertionError(f"Unexpected request: {request.method} {request.url}")

        response = self.responses.popleft()

        if isinstance(response, Exception):
            raise response

        if callable(response):
            return response(request)

        return response

    @property
    def last(self) -> RecordedCall:
        return self.calls[-1]

    def client(self, **options: Any) -> NexiomConnect | AsyncNexiomConnect:
        options.setdefault("base_url", BASE_URL)
        mock = httpx.MockTransport(self.handle)

        if self.mode == "sync":
            return NexiomConnect(API_KEY, http_client=httpx.Client(transport=mock), **options)

        return AsyncNexiomConnect(API_KEY, http_client=httpx.AsyncClient(transport=mock), **options)

    def call(self, operation: Callable[[Any], Any], **options: Any) -> Any:
        """Runs `operation(client)` with a fresh client, awaiting it for the async client."""
        client = self.client(**options)

        if self.mode == "sync":
            return operation(client)

        async def run() -> Any:
            result = operation(client)

            return await result if isinstance(result, Awaitable) else result

        return anyio.run(run)


@pytest.fixture(params=["sync", "async"])
def api(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeApi]:
    fake = FakeApi(mode=request.param)

    # Retry waits are recorded instead of slept, so backoff tests run instantly.
    def sleep(seconds: float) -> None:
        fake.sleeps.append(seconds)

    async def async_sleep(seconds: float) -> None:
        fake.sleeps.append(seconds)

    monkeypatch.setattr(transport, "_sleep", sleep)
    monkeypatch.setattr(transport, "_async_sleep", async_sleep)

    yield fake

    assert not fake.responses, "Queued responses were not used"


@pytest.fixture(autouse=True)
def _no_ambient_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEXIOM_API_KEY", raising=False)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def message(**overrides: Any) -> dict[str, Any]:
    """A WhatsApp message as the API returns it."""
    return {
        "id": "msg_1",
        "channel": "whatsapp",
        "direction": "outbound",
        "type": "template",
        "status": "accepted",
        "sender": "+213555000111",
        "sender_name": "Acme",
        "recipient": "+213555123456",
        "category": "utility",
        "template": {"id": "mtp_1", "name": "order_update", "language": "en_US", "version": 1},
        "is_billable": True,
        "cost": "0.0000",
        "cost_currency": "DZD",
        "failure_code": None,
        "failure_reason": None,
        "created_at": "2026-10-14T09:30:00.000Z",
        "accepted_at": "2026-10-14T09:30:01.000Z",
        "sent_at": None,
        "delivered_at": None,
        "read_at": None,
        "failed_at": None,
        "reply_to": None,
        "contact_name": None,
        "preview": None,
        **overrides,
    }
