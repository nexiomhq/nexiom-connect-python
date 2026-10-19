"""Behavior that needs real sockets: deadlines, slow bodies, and redirects."""

from __future__ import annotations

import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest

from nexiom_connect import AsyncNexiomConnect, ErrorKind, NexiomConnect, NexiomError

from .conftest import API_KEY

if TYPE_CHECKING:
    from collections.abc import Iterator
from typing import Any

PAGE = {"items": [], "total": 0, "page": 1, "limit": 50}

EMAIL: dict[str, Any] = {
    "from_": "hello@example.com",
    "to": "customer@example.com",
    "subject": "Welcome",
    "text": "Thanks for joining us.",
}


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    paths: list[str]


class _Handler(BaseHTTPRequestHandler):
    server: _Server

    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        self._route()

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("content-length", 0)))
        self._route()

    def _route(self) -> None:
        self.server.paths.append(self.path)

        if self.path.startswith("/slow-body"):
            body = json.dumps({"data": PAGE}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()

            for byte in body:
                self.wfile.write(bytes([byte]))
                self.wfile.flush()
                time.sleep(0.05)

            return

        if self.path.startswith("/slow"):
            time.sleep(3)

        if self.path.startswith("/redirect"):
            self.send_response(307)
            self.send_header("location", f"http://127.0.0.1:{self.server.server_port}/target")
            self.send_header("content-length", "0")
            self.end_headers()

            return

        body = json.dumps({"data": PAGE}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def server() -> Iterator[_Server]:
    httpd = _Server(("127.0.0.1", 0), _Handler)
    httpd.paths = []
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    yield httpd

    httpd.shutdown()
    httpd.server_close()


def _url(server: _Server, prefix: str) -> str:
    return f"http://127.0.0.1:{server.server_port}/{prefix}"


def test_slow_server_times_out(server: _Server) -> None:
    with NexiomConnect(API_KEY, base_url=_url(server, "slow"), timeout=0.3) as nexiom:
        started = time.monotonic()

        with pytest.raises(NexiomError) as raised:
            nexiom.emails.send(**EMAIL)

    assert time.monotonic() - started < 1.5
    assert raised.value.kind is ErrorKind.TIMEOUT
    assert raised.value.status is None
    assert re.fullmatch(r"[0-9a-f]{32}", raised.value.response.idempotency_key or "")


@pytest.mark.anyio
async def test_slow_server_times_out_async(server: _Server) -> None:
    async with AsyncNexiomConnect(API_KEY, base_url=_url(server, "slow"), timeout=0.3) as nexiom:
        started = time.monotonic()

        with pytest.raises(NexiomError) as raised:
            await nexiom.emails.send(**EMAIL, idempotency_key="welcome-ada")

    assert time.monotonic() - started < 1.5
    assert raised.value.kind is ErrorKind.TIMEOUT
    assert raised.value.response.idempotency_key == "welcome-ada"


def test_slow_body_times_out(server: _Server) -> None:
    with NexiomConnect(API_KEY, base_url=_url(server, "slow-body"), timeout=0.5) as nexiom:
        started = time.monotonic()

        with pytest.raises(NexiomError) as raised:
            nexiom.contacts.list(max_retries=0)

    assert time.monotonic() - started < 1.5
    assert raised.value.kind is ErrorKind.TIMEOUT


@pytest.mark.anyio
async def test_slow_body_times_out_async(server: _Server) -> None:
    async with AsyncNexiomConnect(
        API_KEY, base_url=_url(server, "slow-body"), timeout=0.5
    ) as nexiom:
        started = time.monotonic()

        with pytest.raises(NexiomError) as raised:
            await nexiom.contacts.list(max_retries=0)

    assert time.monotonic() - started < 1.5
    assert raised.value.kind is ErrorKind.TIMEOUT


def test_redirect_is_not_followed(server: _Server) -> None:
    with (
        NexiomConnect(API_KEY, base_url=_url(server, "redirect")) as nexiom,
        pytest.raises(NexiomError) as raised,
    ):
        nexiom.contacts.list()

    assert raised.value.status == 307
    assert server.paths == ["/redirect/v1/emails/contacts"]


@pytest.mark.anyio
async def test_redirect_is_not_followed_async(server: _Server) -> None:
    async with AsyncNexiomConnect(API_KEY, base_url=_url(server, "redirect")) as nexiom:
        with pytest.raises(NexiomError) as raised:
            await nexiom.contacts.list()

    assert raised.value.status == 307
    assert server.paths == ["/redirect/v1/emails/contacts"]


def test_a_real_round_trip(server: _Server) -> None:
    with NexiomConnect(API_KEY, base_url=_url(server, "api")) as nexiom:
        assert nexiom.contacts.list(limit=5) == PAGE

    assert server.paths == ["/api/v1/emails/contacts?limit=5"]
