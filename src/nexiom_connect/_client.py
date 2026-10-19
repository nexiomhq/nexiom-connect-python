from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from ._resources.contacts import AsyncContacts, Contacts
from ._resources.domains import AsyncDomains, Domains
from ._resources.emails import AsyncEmails, Emails
from ._resources.messaging import AsyncMessaging, Messaging
from ._resources.templates import AsyncTemplates, Templates
from ._resources.webhooks import Webhooks
from ._transport import DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT, AsyncTransport, SyncTransport

if TYPE_CHECKING:
    from types import TracebackType

    import httpx

_Client = TypeVar("_Client", bound="NexiomConnect")

_AsyncClient = TypeVar("_AsyncClient", bound="AsyncNexiomConnect")


class NexiomConnect:
    """The Nexiom Connect API client.

    ```python
    from nexiom_connect import NexiomConnect

    nexiom = NexiomConnect()  # Reads NEXIOM_API_KEY.
    ```

    The client is thread-safe and keeps connections open: create one and reuse it, and close it
    with `close()` or a `with` block when you are done.
    """

    emails: Emails
    contacts: Contacts
    templates: Templates
    domains: Domains

    messaging: Messaging
    """Messages on every messaging channel, such as WhatsApp."""

    webhooks: Webhooks
    """Webhook verification; makes no network request."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.Client | None = None,
    ) -> None:
        """Creates a client.

        Args:
            api_key: An API key from the Nexiom Connect dashboard. Default: the `NEXIOM_API_KEY`
                environment variable. Keep it on the server.
            base_url: API root without a version prefix. Default: https://api-connect.nxiom.com/api.
            timeout: Total request deadline in seconds, including retries. Default: 30.
            max_retries: Additional attempts for reads, idempotent sends, cancels, and domain
                verification only. Default: 2.
            http_client: An `httpx.Client` for proxies, instrumentation, or testing. The SDK never
                closes a client it did not create.

        Raises:
            NexiomValidationError: When an argument is invalid or no API key is found.
        """
        self._transport = SyncTransport(api_key, base_url, timeout, max_retries, http_client)

        self.emails = Emails(self._transport)
        self.contacts = Contacts(self._transport)
        self.templates = Templates(self._transport)
        self.domains = Domains(self._transport)
        self.messaging = Messaging(self._transport)
        self.webhooks = Webhooks()

    @property
    def base_url(self) -> str:
        return self._transport.base_url

    def close(self) -> None:
        """Closes the client's connections. Does nothing to an `http_client` you passed in."""
        self._transport.close()

    def __enter__(self: _Client) -> _Client:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"NexiomConnect(base_url={self._transport.base_url!r})"


class AsyncNexiomConnect:
    """The Nexiom Connect API client for asyncio and trio.

    ```python
    from nexiom_connect import AsyncNexiomConnect

    nexiom = AsyncNexiomConnect()  # Reads NEXIOM_API_KEY.
    ```

    Create one client and reuse it, and close it with `await close()` or an `async with` block
    when you are done.
    """

    emails: AsyncEmails
    contacts: AsyncContacts
    templates: AsyncTemplates
    domains: AsyncDomains

    messaging: AsyncMessaging
    """Messages on every messaging channel, such as WhatsApp."""

    webhooks: Webhooks
    """Webhook verification; makes no network request."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Creates a client.

        Args:
            api_key: An API key from the Nexiom Connect dashboard. Default: the `NEXIOM_API_KEY`
                environment variable. Keep it on the server.
            base_url: API root without a version prefix. Default: https://api-connect.nxiom.com/api.
            timeout: Total request deadline in seconds, including retries. Default: 30.
            max_retries: Additional attempts for reads, idempotent sends, cancels, and domain
                verification only. Default: 2.
            http_client: An `httpx.AsyncClient` for proxies, instrumentation, or testing. The SDK
                never closes a client it did not create.

        Raises:
            NexiomValidationError: When an argument is invalid or no API key is found.
        """
        self._transport = AsyncTransport(api_key, base_url, timeout, max_retries, http_client)

        self.emails = AsyncEmails(self._transport)
        self.contacts = AsyncContacts(self._transport)
        self.templates = AsyncTemplates(self._transport)
        self.domains = AsyncDomains(self._transport)
        self.messaging = AsyncMessaging(self._transport)
        self.webhooks = Webhooks()

    @property
    def base_url(self) -> str:
        return self._transport.base_url

    async def close(self) -> None:
        """Closes the client's connections. Does nothing to an `http_client` you passed in."""
        await self._transport.close()

    async def __aenter__(self: _AsyncClient) -> _AsyncClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    def __repr__(self) -> str:
        return f"AsyncNexiomConnect(base_url={self._transport.base_url!r})"
