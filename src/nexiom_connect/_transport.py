"""Shared HTTP transport: authentication, retries, deadlines, and response parsing."""

from __future__ import annotations

import json
import math
import os
import random
import re
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any, Final, Literal
from urllib.parse import urlsplit

import anyio
import httpx

from ._errors import ErrorKind, NexiomError, NexiomValidationError, ResponseMetadata
from ._validate import integer
from ._version import __version__

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator, Mapping

DEFAULT_BASE_URL: Final = "https://api-connect.nxiom.com/api"

DEFAULT_TIMEOUT: Final = 30.0

DEFAULT_MAX_RETRIES: Final = 2

API_KEY_ENVIRONMENT_VARIABLE: Final = "NEXIOM_API_KEY"

_RETRY_STATUSES: Final = frozenset({408, 429, 500, 502, 503, 504})

# Seconds; matches the Node.js SDK's 2^31 - 1 millisecond limit.
_MAX_TIMEOUT: Final = 2147483.647

_MAX_RETRIES: Final = 10

_LOOPBACK_HOSTS: Final = frozenset({"localhost", "127.0.0.1", "::1"})

_API_KEY: Final = re.compile(r"[\x21-\x7e]+", re.ASCII)

_NUMBER: Final = re.compile(r"-?[0-9]+(?:\.[0-9]+)?", re.ASCII)

_USER_AGENT: Final = f"nexiom-connect-python/{__version__}"

Method = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


@dataclass(frozen=True)
class Request:
    """One API operation, described independently of the sync or async client that sends it."""

    method: Method
    path: str
    query: Mapping[str, str | int] | None = None
    body: Mapping[str, Any] | None = None
    idempotency_key: str | None = None

    retryable: bool | None = None
    """Safe to repeat. Default: GET requests and requests with an idempotency key."""

    envelope: bool = True
    """False for endpoints that return the resource without a `data` wrapper."""

    accepts: Callable[[Any], bool] | None = None
    """Checks the shape of a successful payload."""

    transform: Callable[[Any], Any] | None = None
    """Turns the checked payload into the method's result."""


@dataclass(frozen=True)
class _Prepared:
    request: Request
    url: str
    headers: dict[str, str]
    content: bytes | None
    deadline: float
    max_retries: int
    retryable: bool


class _Secret:
    """Holds the API key so `repr()`, `vars()`, and logged locals never show it."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def bearer(self) -> str:
        return f"Bearer {self._value}"

    def __repr__(self) -> str:
        return "<redacted>"

    __str__ = __repr__

    def __reduce__(self) -> Any:
        raise TypeError("The Nexiom Connect API key cannot be pickled")


class _DeadlineExceededError(Exception):
    pass


class BaseTransport:
    def __init__(
        self,
        api_key: str | None,
        base_url: str | None,
        timeout: float,
        max_retries: int,
    ) -> None:
        self._api_key = _Secret(_api_key(api_key))
        self.base_url = _base_url(DEFAULT_BASE_URL if base_url is None else base_url)
        self.timeout = _timeout(timeout)
        self.max_retries = _max_retries(max_retries)

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(base_url={self.base_url!r}, timeout={self.timeout!r}, "
            f"max_retries={self.max_retries!r})"
        )

    def _prepare(
        self, request: Request, timeout: float | None, max_retries: int | None
    ) -> _Prepared:
        """Checks the per-request options and serializes the body before any network work."""
        resolved_timeout = self.timeout if timeout is None else _timeout(timeout)
        resolved_retries = self.max_retries if max_retries is None else _max_retries(max_retries)

        content = None if request.body is None else _json(request.body)

        headers = {
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        }

        if content is not None:
            headers["Content-Type"] = "application/json"

        if request.idempotency_key is not None:
            headers["Idempotency-Key"] = request.idempotency_key

        retryable = request.retryable
        if retryable is None:
            retryable = request.method == "GET" or request.idempotency_key is not None

        return _Prepared(
            request=request,
            url=self.base_url + request.path,
            headers=headers,
            content=content,
            deadline=_now() + resolved_timeout,
            max_retries=resolved_retries,
            retryable=retryable,
        )

    def _should_retry(self, prepared: _Prepared, error: NexiomError, attempt: int) -> float | None:
        """Seconds to wait before the next attempt, or `None` to raise the error now."""
        if not prepared.retryable or attempt >= prepared.max_retries or not _is_retryable(error):
            return None

        # A wait that cannot finish before the deadline would only turn this error into a timeout.
        delay = _retry_delay(error.response.headers, attempt)
        if delay >= prepared.deadline - _now():
            return None

        return delay

    def _remaining(self, prepared: _Prepared) -> float:
        remaining = prepared.deadline - _now()

        if remaining <= 0:
            raise _failure(prepared, ErrorKind.TIMEOUT)

        return remaining

    def _build(
        self, client: httpx.Client | httpx.AsyncClient, prepared: _Prepared, remaining: float
    ) -> httpx.Request:
        # The key goes straight into httpx.Headers, whose repr() hides Authorization.
        return client.build_request(
            prepared.request.method,
            prepared.url,
            params=prepared.request.query,
            headers={**prepared.headers, "Authorization": self._api_key.bearer()},
            content=prepared.content,
            timeout=httpx.Timeout(remaining),
        )


class SyncTransport(BaseTransport):
    def __init__(
        self,
        api_key: str | None,
        base_url: str | None,
        timeout: float,
        max_retries: int,
        http_client: httpx.Client | None,
    ) -> None:
        if http_client is not None and not isinstance(http_client, httpx.Client):
            raise NexiomValidationError("http_client must be an httpx.Client")

        super().__init__(api_key, base_url, timeout, max_retries)

        self._owns_client = http_client is None
        self._http = http_client if http_client is not None else httpx.Client()

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def request(self, request: Request, *, timeout: float | None, max_retries: int | None) -> Any:
        prepared = self._prepare(request, timeout, max_retries)

        attempt = 0
        while True:
            try:
                return self._attempt(prepared)
            except NexiomError as error:
                delay = self._should_retry(prepared, error, attempt)
                if delay is None:
                    raise

            _sleep(delay)
            attempt += 1

    def _attempt(self, prepared: _Prepared) -> Any:
        remaining = self._remaining(prepared)
        failure: ErrorKind | None = None

        try:
            response = self._http.send(
                self._build(self._http, prepared, remaining),
                stream=True,
                follow_redirects=False,
                auth=None,
            )

            try:
                content = _read(response.iter_bytes(), prepared.deadline)
            finally:
                response.close()
        except httpx.TimeoutException:
            failure = ErrorKind.TIMEOUT
        except _DeadlineExceededError:
            failure = ErrorKind.TIMEOUT
        except httpx.RequestError:
            failure = (
                ErrorKind.TIMEOUT if prepared.deadline - _now() <= 0.005 else ErrorKind.NETWORK
            )

        # Raised outside the except blocks, so neither __cause__ nor __context__ holds the
        # transport exception, its request, or the Authorization header.
        if failure is not None:
            raise _failure(prepared, failure)

        return _parse(response, content, prepared)


class AsyncTransport(BaseTransport):
    def __init__(
        self,
        api_key: str | None,
        base_url: str | None,
        timeout: float,
        max_retries: int,
        http_client: httpx.AsyncClient | None,
    ) -> None:
        if http_client is not None and not isinstance(http_client, httpx.AsyncClient):
            raise NexiomValidationError("http_client must be an httpx.AsyncClient")

        super().__init__(api_key, base_url, timeout, max_retries)

        self._owns_client = http_client is None
        self._http = http_client if http_client is not None else httpx.AsyncClient()

    async def close(self) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def request(
        self, request: Request, *, timeout: float | None, max_retries: int | None
    ) -> Any:
        prepared = self._prepare(request, timeout, max_retries)

        attempt = 0
        while True:
            try:
                return await self._attempt(prepared)
            except NexiomError as error:
                delay = self._should_retry(prepared, error, attempt)
                if delay is None:
                    raise

            await _async_sleep(delay)
            attempt += 1

    async def _attempt(self, prepared: _Prepared) -> Any:
        remaining = self._remaining(prepared)
        failure: ErrorKind | None = None

        # Cancellation (asyncio.CancelledError, trio.Cancelled) is a BaseException and passes through.
        try:
            response = await self._http.send(
                self._build(self._http, prepared, remaining),
                stream=True,
                follow_redirects=False,
                auth=None,
            )

            try:
                content = await _async_read(response.aiter_bytes(), prepared.deadline)
            finally:
                await response.aclose()
        except httpx.TimeoutException:
            failure = ErrorKind.TIMEOUT
        except _DeadlineExceededError:
            failure = ErrorKind.TIMEOUT
        except httpx.RequestError:
            failure = (
                ErrorKind.TIMEOUT if prepared.deadline - _now() <= 0.005 else ErrorKind.NETWORK
            )

        if failure is not None:
            raise _failure(prepared, failure)

        return _parse(response, content, prepared)


def _now() -> float:
    return time.monotonic()


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


async def _async_sleep(seconds: float) -> None:
    await anyio.sleep(seconds)


def _read(chunks: Iterator[bytes], deadline: float) -> bytes:
    """Reads the body, failing once the deadline passes, so a slow body cannot stall the call."""
    body = bytearray()

    for chunk in chunks:
        body += chunk

        if _now() > deadline:
            raise _DeadlineExceededError

    return bytes(body)


async def _async_read(chunks: AsyncIterator[bytes], deadline: float) -> bytes:
    body = bytearray()

    async for chunk in chunks:
        body += chunk

        if _now() > deadline:
            raise _DeadlineExceededError

    return bytes(body)


def _failure(prepared: _Prepared, kind: ErrorKind) -> NexiomError:
    metadata = ResponseMetadata(idempotency_key=prepared.request.idempotency_key)

    if kind is ErrorKind.TIMEOUT:
        return NexiomError("Request timed out", kind, metadata)

    return NexiomError("Unable to complete the API request", kind, metadata)


def _parse(response: httpx.Response, content: bytes, prepared: _Prepared) -> Any:
    request = prepared.request
    status = response.status_code

    headers: dict[str, tuple[str, ...]] = {}
    for name, value in response.headers.multi_items():
        key = name.lower()
        headers[key] = (*headers.get(key, ()), value)

    try:
        payload: Any = json.loads(content) if content else None
    except ValueError:
        payload = None

    fields: dict[str, Any] = payload if isinstance(payload, dict) else {}

    request_id = _first(headers, "x-request-id") or _first(headers, "x-correlation-id")
    if isinstance(fields.get("correlationId"), str):
        request_id = fields["correlationId"]

    metadata = ResponseMetadata(
        status=status,
        headers=headers,
        request_id=request_id,
        idempotency_key=request.idempotency_key,
    )

    if 200 <= status < 300:
        if not _is_valid_success(payload, envelope=request.envelope):
            raise NexiomError(
                "API returned an empty or invalid JSON response",
                ErrorKind.PROTOCOL,
                metadata,
            )

        # Resource endpoints return { data }, deletes return { success }, and a few detail
        # endpoints return the resource itself.
        data = fields["data"] if request.envelope and "data" in fields else fields

        if request.accepts is not None and not request.accepts(data):
            raise NexiomError("API returned an unexpected response", ErrorKind.PROTOCOL, metadata)

        return data if request.transform is None else request.transform(data)

    message = fields.get("message")
    if not isinstance(message, str):
        message = f"Request failed with HTTP {status}"

    code = fields.get("code")
    if not isinstance(code, str):
        error = fields.get("error")
        code = error if isinstance(error, str) else None

    raise NexiomError(message, ErrorKind.API, metadata, code, fields.get("details"))


def _is_valid_success(payload: object, *, envelope: bool) -> bool:
    if not isinstance(payload, dict):
        return False

    if not envelope:
        return True

    if "data" in payload:
        return isinstance(payload["data"], (dict, list))

    return isinstance(payload.get("success"), bool)


def _first(headers: Mapping[str, tuple[str, ...]], name: str) -> str | None:
    values = headers.get(name)

    return values[0] if values else None


def _is_retryable(error: NexiomError) -> bool:
    return error.kind is ErrorKind.NETWORK or (
        error.kind is ErrorKind.API and error.status in _RETRY_STATUSES
    )


def _retry_delay(headers: Mapping[str, tuple[str, ...]], attempt: int) -> float:
    """Seconds to wait before the next attempt, from Retry-After or exponential backoff with jitter."""
    value = (_first(headers, "retry-after") or "").strip()

    if value:
        delay: float | None = None

        if _NUMBER.fullmatch(value):
            delay = float(value)
        else:
            try:
                delay = parsedate_to_datetime(value).timestamp() - time.time()
            except (TypeError, ValueError, IndexError, OverflowError):
                delay = None

        if delay is not None and math.isfinite(delay):
            return min(_MAX_TIMEOUT, max(0.0, delay))

    jitter = 0.75 + random.random() * 0.25  # noqa: S311 - backoff jitter, not a secret.

    return float(min(8.0, 0.5 * 2**attempt) * jitter)


def _json(body: Mapping[str, Any]) -> bytes:
    try:
        text = json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False)

        return text.encode("utf-8")
    except (TypeError, ValueError):
        raise NexiomValidationError("Request body must be JSON serializable") from None


def _api_key(value: object) -> str:
    if value is None:
        value = os.environ.get(API_KEY_ENVIRONMENT_VARIABLE)

        if value is None:
            raise NexiomValidationError(
                f"api_key is required: pass it to the client or set {API_KEY_ENVIRONMENT_VARIABLE}",
            )

    if not isinstance(value, str) or _API_KEY.fullmatch(value) is None:
        raise NexiomValidationError(
            "api_key must be a non-empty string of printable ASCII without whitespace",
        )

    return value


def _timeout(value: object) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value < 0.001
        or value > _MAX_TIMEOUT
    ):
        raise NexiomValidationError(
            f"timeout must be a number of seconds between 0.001 and {_MAX_TIMEOUT}",
        )

    return float(value)


def _max_retries(value: object) -> int:
    return integer(value, "max_retries", 0, _MAX_RETRIES)


def _base_url(value: object) -> str:
    if not isinstance(value, str) or re.search(r"[\s\x00-\x1f\x7f]", value):
        raise NexiomValidationError("base_url must be an absolute HTTP(S) URL")

    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").lower()
        username, password = parts.username, parts.password
    except ValueError:
        raise NexiomValidationError("base_url must be an absolute HTTP(S) URL") from None

    scheme = parts.scheme.lower()

    if scheme not in {"http", "https"} or host == "":
        raise NexiomValidationError("base_url must be an absolute HTTP(S) URL")

    if username is not None or password is not None or "?" in value or "#" in value:
        raise NexiomValidationError(
            "base_url must be an HTTP(S) URL without credentials, query, or fragment",
        )

    if scheme == "http" and host not in _LOOPBACK_HOSTS:
        raise NexiomValidationError("base_url must use HTTPS except on loopback hosts")

    return value.rstrip("/")
