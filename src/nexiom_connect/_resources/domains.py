"""Add, verify, list, and delete sending domains."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from .. import _validate as validate
from .._errors import NexiomValidationError
from .._transport import Request
from ._base import AsyncResource, SyncResource

if TYPE_CHECKING:
    from ..types import DeleteResponse, Domain, DomainStatus, ListDomainsResponse

_PATH = "/v1/emails/domains"

# The API bounds page offsets; narrow larger collections with filters or search.
_MAX_PAGE = 10_000

_STATUSES = ("pending", "verified", "failed")


def _create(*, domain: object, open_tracking: object) -> Request:
    body: dict[str, Any] = {
        "domain": validate.non_empty(domain, "domain"),
    }

    if open_tracking is not None:
        if not isinstance(open_tracking, bool):
            raise NexiomValidationError("open_tracking must be a boolean")

        body["openTracking"] = open_tracking

    return Request("POST", _PATH, body=body)


def _list(*, page: object, limit: object, status: object, search: object) -> Request:
    query = validate.query(
        {
            "page": validate.optional_integer(page, "page", 1, _MAX_PAGE),
            "limit": validate.optional_integer(limit, "limit", 1, 100),
            "status": validate.optional_one_of(status, "status", _STATUSES),
            "search": validate.optional_string(search, "search"),
        },
    )

    return Request("GET", _PATH, query=query)


def _path(domain_id: object) -> str:
    return f"{_PATH}/{validate.resource_id(domain_id, 'domain_id')}"


class Domains(SyncResource):
    """Add, verify, list, and delete sending domains."""

    def create(
        self,
        *,
        domain: str,
        open_tracking: bool | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Domain:
        """Adds a sending subdomain, such as `mail.example.com`, and returns the DNS records to publish.

        Root domains are rejected by the API.
        """
        request = _create(domain=domain, open_tracking=open_tracking)

        return cast(
            "Domain", self._transport.request(request, timeout=timeout, max_retries=max_retries)
        )

    def list(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
        status: DomainStatus | None = None,
        search: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> ListDomainsResponse:
        """Lists sending domains, 50 per page by default and at most 100."""
        request = _list(page=page, limit=limit, status=status, search=search)

        return cast(
            "ListDomainsResponse",
            self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    def get(
        self,
        domain_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Domain:
        """Gets a sending domain with its DNS records."""
        request = Request("GET", _path(domain_id))

        return cast(
            "Domain", self._transport.request(request, timeout=timeout, max_retries=max_retries)
        )

    def verify(
        self,
        domain_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Domain:
        """Checks the domain's DNS records now.

        A successful call means the check ran; read `status` before sending. Checking twice is
        safe, so the call is retried like a read.
        """
        request = Request("POST", f"{_path(domain_id)}/verify", retryable=True)

        return cast(
            "Domain", self._transport.request(request, timeout=timeout, max_retries=max_retries)
        )

    def delete(
        self,
        domain_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> DeleteResponse:
        """Deletes a sending domain. This affects future sends that use it."""
        request = Request("DELETE", _path(domain_id))

        return cast(
            "DeleteResponse",
            self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )


class AsyncDomains(AsyncResource):
    """Add, verify, list, and delete sending domains."""

    async def create(
        self,
        *,
        domain: str,
        open_tracking: bool | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Domain:
        """Adds a sending subdomain, such as `mail.example.com`, and returns the DNS records to publish.

        Root domains are rejected by the API.
        """
        request = _create(domain=domain, open_tracking=open_tracking)

        return cast(
            "Domain",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    async def list(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
        status: DomainStatus | None = None,
        search: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> ListDomainsResponse:
        """Lists sending domains, 50 per page by default and at most 100."""
        request = _list(page=page, limit=limit, status=status, search=search)

        return cast(
            "ListDomainsResponse",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    async def get(
        self,
        domain_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Domain:
        """Gets a sending domain with its DNS records."""
        request = Request("GET", _path(domain_id))

        return cast(
            "Domain",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    async def verify(
        self,
        domain_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Domain:
        """Checks the domain's DNS records now.

        A successful call means the check ran; read `status` before sending. Checking twice is
        safe, so the call is retried like a read.
        """
        request = Request("POST", f"{_path(domain_id)}/verify", retryable=True)

        return cast(
            "Domain",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    async def delete(
        self,
        domain_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> DeleteResponse:
        """Deletes a sending domain. This affects future sends that use it."""
        request = Request("DELETE", _path(domain_id))

        return cast(
            "DeleteResponse",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )
