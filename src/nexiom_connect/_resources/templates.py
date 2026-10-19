"""Read email templates, their variables, and their version history."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from .. import _validate as validate
from .._transport import Request
from ._base import AsyncResource, SyncResource

if TYPE_CHECKING:
    import builtins

    from ..types import (
        ListTemplatesResponse,
        Template,
        TemplateListStatus,
        TemplateOrigin,
        TemplateVariable,
        TemplateVersion,
    )

_PATH = "/v1/emails/templates"

# The API bounds page offsets; narrow larger collections with filters or search.
_MAX_PAGE = 10_000

_STATUSES = ("draft", "published", "changes_in_draft", "archived")

_ORIGINS = ("custom", "prebuilt")


def _list(
    *,
    page: object,
    limit: object,
    status: object,
    search: object,
    origin: object,
    category: object,
) -> Request:
    query = validate.query(
        {
            "page": validate.optional_integer(page, "page", 1, _MAX_PAGE),
            "limit": validate.optional_integer(limit, "limit", 1, 100),
            "status": validate.optional_one_of(status, "status", _STATUSES),
            "search": validate.optional_string(search, "search"),
            "origin": validate.optional_one_of(origin, "origin", _ORIGINS),
            "category": validate.optional_string(category, "category"),
        },
    )

    return Request("GET", _PATH, query=query)


def _get(template_id: object) -> Request:
    return Request("GET", f"{_PATH}/{validate.resource_id(template_id, 'template_id')}")


def _variables(template_id: object) -> Request:
    path = f"{_PATH}/{validate.resource_id(template_id, 'template_id')}/variables"

    return Request("GET", path, accepts=validate.is_list_of_objects)


def _versions(template_id: object, *, limit: object, before_version: object) -> Request:
    path = f"{_PATH}/{validate.resource_id(template_id, 'template_id')}/versions"

    query = validate.query(
        {
            "limit": validate.optional_integer(limit, "limit", 1, 100),
            "beforeVersion": validate.optional_integer(before_version, "before_version", 1),
        },
    )

    return Request("GET", path, query=query, accepts=validate.is_list_of_objects)


class Templates(SyncResource):
    """Read email templates, their variables, and their version history."""

    def list(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
        status: TemplateListStatus | None = None,
        search: str | None = None,
        origin: TemplateOrigin | None = None,
        category: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> ListTemplatesResponse:
        """Lists templates, most recently updated first, 50 per page by default and at most 100."""
        request = _list(
            page=page,
            limit=limit,
            status=status,
            search=search,
            origin=origin,
            category=category,
        )

        return cast(
            "ListTemplatesResponse",
            self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    def get(
        self,
        template_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Template:
        """Gets a template with its published and draft versions."""
        request = _get(template_id)

        return cast(
            "Template", self._transport.request(request, timeout=timeout, max_retries=max_retries)
        )

    def variables(
        self,
        template_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> builtins.list[TemplateVariable]:
        """Lists a template's variables, ordered by key.

        Returns the draft's variables when the template has one, otherwise the published
        version's. Sends use `published_version["variables"]` from `get()`.
        """
        request = _variables(template_id)

        return cast(
            "builtins.list[TemplateVariable]",
            self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    def versions(
        self,
        template_id: str,
        *,
        limit: int | None = None,
        before_version: int | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> builtins.list[TemplateVersion]:
        """Lists a template's versions, newest first.

        For older versions, pass the last `version_number` as `before_version`; a response with
        fewer than `limit` versions is the last.
        """
        request = _versions(template_id, limit=limit, before_version=before_version)

        return cast(
            "builtins.list[TemplateVersion]",
            self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )


class AsyncTemplates(AsyncResource):
    """Read email templates, their variables, and their version history."""

    async def list(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
        status: TemplateListStatus | None = None,
        search: str | None = None,
        origin: TemplateOrigin | None = None,
        category: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> ListTemplatesResponse:
        """Lists templates, most recently updated first, 50 per page by default and at most 100."""
        request = _list(
            page=page,
            limit=limit,
            status=status,
            search=search,
            origin=origin,
            category=category,
        )

        return cast(
            "ListTemplatesResponse",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    async def get(
        self,
        template_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Template:
        """Gets a template with its published and draft versions."""
        request = _get(template_id)

        return cast(
            "Template",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    async def variables(
        self,
        template_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> builtins.list[TemplateVariable]:
        """Lists a template's variables, ordered by key.

        Returns the draft's variables when the template has one, otherwise the published
        version's. Sends use `published_version["variables"]` from `get()`.
        """
        request = _variables(template_id)

        return cast(
            "builtins.list[TemplateVariable]",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    async def versions(
        self,
        template_id: str,
        *,
        limit: int | None = None,
        before_version: int | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> builtins.list[TemplateVersion]:
        """Lists a template's versions, newest first.

        For older versions, pass the last `version_number` as `before_version`; a response with
        fewer than `limit` versions is the last.
        """
        request = _versions(template_id, limit=limit, before_version=before_version)

        return cast(
            "builtins.list[TemplateVersion]",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )
