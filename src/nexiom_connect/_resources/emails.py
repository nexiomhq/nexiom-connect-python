"""Send emails, manage scheduled sends, and read email logs and suppressions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, cast

from .. import _validate as validate
from .._errors import NexiomValidationError
from .._transport import Request
from ._base import AsyncResource, SyncResource

if TYPE_CHECKING:
    import datetime as dt

    from .._transport import AsyncTransport, SyncTransport
    from ..types import (
        CancelEmailResponse,
        Email,
        EmailSource,
        EmailStatus,
        ListEmailsResponse,
        ListEmailSuppressionsResponse,
        RescheduleEmailResponse,
        SendEmailResponse,
    )

_PATH = "/v1/emails"

_SUPPRESSIONS_PATH = "/v1/emails/suppressions"

_MAX_EMAIL_IDEMPOTENCY_KEY = 128


def _send(
    *,
    from_: object,
    to: object,
    subject: object,
    html: object,
    text: object,
    from_name: object,
    cc: object,
    bcc: object,
    reply_to: object,
    template_id: object,
    template_variables: object,
    metadata: object,
    scheduled_at: object,
    idempotency_key: object,
) -> Request:
    validate.non_empty(from_, "from_")
    validate.optional_string(from_name, "from_name")
    validate.optional_string(reply_to, "reply_to")

    recipients = _addresses(to, "to")
    copies = None if cc is None else _addresses(cc, "cc")
    blind_copies = None if bcc is None else _addresses(bcc, "bcc")

    template = validate.optional_string(template_id, "template_id")
    validate.optional_string(subject, "subject")
    validate.optional_string(html, "html")
    validate.optional_string(text, "text")

    if not template:
        validate.non_empty(subject, "subject")

        if not (isinstance(html, str) and html.strip()) and not (
            isinstance(text, str) and text.strip()
        ):
            raise NexiomValidationError("html, text, or template_id is required")

    if isinstance(recipients, list) and len(recipients) > 1 and (copies or blind_copies):
        raise NexiomValidationError("CC and BCC require one primary recipient")

    key = validate.idempotency_key(idempotency_key, _MAX_EMAIL_IDEMPOTENCY_KEY)

    body = _present(
        {
            "from": from_,
            "fromName": from_name,
            "to": recipients,
            "cc": copies,
            "bcc": blind_copies,
            "replyTo": reply_to,
            "subject": subject,
            "html": html,
            "text": text,
            "templateId": template_id,
            "templateVariables": validate.optional_map(template_variables, "template_variables"),
            "metadata": validate.optional_map(metadata, "metadata"),
            "scheduledAt": validate.optional_timestamp(scheduled_at, "scheduled_at"),
        },
    )

    return Request("POST", f"{_PATH}/send", body=body, idempotency_key=key)


def _cancel(message_id: object) -> Request:
    path = f"{_PATH}/messages/{validate.resource_id(message_id, 'message_id')}/cancel"

    return Request("POST", path, retryable=True)


def _reschedule(message_id: object, scheduled_at: object) -> Request:
    path = f"{_PATH}/messages/{validate.resource_id(message_id, 'message_id')}"

    body = {
        "scheduledAt": validate.timestamp(scheduled_at, "scheduled_at"),
    }

    return Request("PATCH", path, body=body)


def _list(
    *,
    limit: object,
    cursor: object,
    status: object,
    source: object,
    recipient: object,
    search: object,
    contact_id: object,
    template_id: object,
    start_date: object,
    end_date: object,
) -> Request:
    page_cursor = validate.optional_string(cursor, "cursor")
    if page_cursor is not None and len(page_cursor) > 1024:
        raise NexiomValidationError("cursor must contain at most 1024 characters")

    query = validate.query(
        {
            "limit": validate.optional_integer(limit, "limit", 1, 100),
            "cursor": page_cursor,
            "status": validate.optional_string(status, "status"),
            "source": validate.optional_string(source, "source"),
            "recipient": validate.optional_string(recipient, "recipient"),
            "search": validate.optional_string(search, "search"),
            "contactId": validate.optional_string(contact_id, "contact_id"),
            "templateId": validate.optional_string(template_id, "template_id"),
            "startDate": validate.optional_timestamp(start_date, "start_date"),
            "endDate": validate.optional_timestamp(end_date, "end_date"),
        },
    )

    return Request("GET", f"{_PATH}/logs", query=query)


def _get(delivery_id: object) -> Request:
    path = f"{_PATH}/logs/{validate.resource_id(delivery_id, 'delivery_id')}"

    return Request("GET", path, envelope=False)


def _list_suppressions(*, search: object, limit: object, cursor: object) -> Request:
    term = validate.optional_string(search, "search")
    if term is not None:
        term = term.strip()

        if term == "" or len(term) > 255:
            raise NexiomValidationError("search must contain 1 to 255 characters")

    page_cursor = validate.optional_string(cursor, "cursor")
    if page_cursor is not None and (page_cursor == "" or len(page_cursor) > 400):
        raise NexiomValidationError("cursor must contain 1 to 400 characters")

    query = validate.query(
        {
            "search": term,
            "limit": validate.optional_integer(limit, "limit", 1, 100),
            "cursor": page_cursor,
        },
    )

    return Request("GET", _SUPPRESSIONS_PATH, query=query)


def _addresses(value: object, name: str) -> str | list[str]:
    """One address, or a list of 1 to 100; `bytes` and other non-text sequences are refused."""
    if isinstance(value, str):
        validate.non_empty(value, name)

        return value

    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
        raise NexiomValidationError(f"{name} must be an address or a list of 1 to 100 addresses")

    addresses = list(value)

    if not 1 <= len(addresses) <= 100:
        raise NexiomValidationError(f"{name} must contain 1 to 100 addresses")

    for address in addresses:
        validate.non_empty(address, name)

    return cast("list[str]", addresses)


def _present(values: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


class EmailSuppressions(SyncResource):
    """Read the addresses this project cannot send to, and why."""

    def list(
        self,
        *,
        search: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> ListEmailSuppressionsResponse:
        """Lists suppressed addresses alphabetically, 50 per page by default and at most 100.

        Pass `nextCursor` as `cursor` while `hasMore` is true.
        """
        request = _list_suppressions(search=search, limit=limit, cursor=cursor)

        return cast(
            "ListEmailSuppressionsResponse",
            self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )


class AsyncEmailSuppressions(AsyncResource):
    """Read the addresses this project cannot send to, and why."""

    async def list(
        self,
        *,
        search: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> ListEmailSuppressionsResponse:
        """Lists suppressed addresses alphabetically, 50 per page by default and at most 100.

        Pass `nextCursor` as `cursor` while `hasMore` is true.
        """
        request = _list_suppressions(search=search, limit=limit, cursor=cursor)

        return cast(
            "ListEmailSuppressionsResponse",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )


class Emails(SyncResource):
    """Send emails, manage scheduled sends, and read email logs."""

    def __init__(self, transport: SyncTransport) -> None:
        super().__init__(transport)

        self.suppressions = EmailSuppressions(transport)

    def send(
        self,
        *,
        from_: str,
        to: str | Sequence[str],
        subject: str | None = None,
        html: str | None = None,
        text: str | None = None,
        from_name: str | None = None,
        cc: str | Sequence[str] | None = None,
        bcc: str | Sequence[str] | None = None,
        reply_to: str | None = None,
        template_id: str | None = None,
        template_variables: Mapping[str, str | int | float | bool] | None = None,
        metadata: Mapping[str, Any] | None = None,
        scheduled_at: dt.datetime | str | None = None,
        idempotency_key: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> SendEmailResponse:
        """Queues an email for delivery, now or at `scheduled_at`.

        Acceptance means queued or scheduled, not delivered. Without an `idempotency_key`, the SDK
        generates one and reuses it for automatic retries.
        """
        request = _send(
            from_=from_,
            to=to,
            subject=subject,
            html=html,
            text=text,
            from_name=from_name,
            cc=cc,
            bcc=bcc,
            reply_to=reply_to,
            template_id=template_id,
            template_variables=template_variables,
            metadata=metadata,
            scheduled_at=scheduled_at,
            idempotency_key=idempotency_key,
        )

        return cast(
            "SendEmailResponse",
            self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    def cancel(
        self,
        message_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> CancelEmailResponse:
        """Cancels every scheduled delivery of a message. Canceling twice returns the same result."""
        request = _cancel(message_id)

        return cast(
            "CancelEmailResponse",
            self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    def reschedule(
        self,
        message_id: str,
        *,
        scheduled_at: dt.datetime | str,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> RescheduleEmailResponse:
        """Moves every scheduled delivery of a message to a new send time."""
        request = _reschedule(message_id, scheduled_at)

        return cast(
            "RescheduleEmailResponse",
            self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    def list(
        self,
        *,
        limit: int | None = None,
        cursor: str | None = None,
        status: EmailStatus | None = None,
        source: EmailSource | None = None,
        recipient: str | None = None,
        search: str | None = None,
        contact_id: str | None = None,
        template_id: str | None = None,
        start_date: dt.date | str | None = None,
        end_date: dt.date | str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> ListEmailsResponse:
        """Lists recipient deliveries, newest first. Pass `nextCursor` as `cursor` for the next page."""
        request = _list(
            limit=limit,
            cursor=cursor,
            status=status,
            source=source,
            recipient=recipient,
            search=search,
            contact_id=contact_id,
            template_id=template_id,
            start_date=start_date,
            end_date=end_date,
        )

        return cast(
            "ListEmailsResponse",
            self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    def get(
        self,
        delivery_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Email:
        """Fetches one recipient delivery, with its content and history, by delivery ID.

        Takes a delivery ID from `deliveryIds` or `list()`, not a message ID.
        """
        request = _get(delivery_id)

        return cast(
            "Email", self._transport.request(request, timeout=timeout, max_retries=max_retries)
        )


class AsyncEmails(AsyncResource):
    """Send emails, manage scheduled sends, and read email logs."""

    def __init__(self, transport: AsyncTransport) -> None:
        super().__init__(transport)

        self.suppressions = AsyncEmailSuppressions(transport)

    async def send(
        self,
        *,
        from_: str,
        to: str | Sequence[str],
        subject: str | None = None,
        html: str | None = None,
        text: str | None = None,
        from_name: str | None = None,
        cc: str | Sequence[str] | None = None,
        bcc: str | Sequence[str] | None = None,
        reply_to: str | None = None,
        template_id: str | None = None,
        template_variables: Mapping[str, str | int | float | bool] | None = None,
        metadata: Mapping[str, Any] | None = None,
        scheduled_at: dt.datetime | str | None = None,
        idempotency_key: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> SendEmailResponse:
        """Queues an email for delivery, now or at `scheduled_at`.

        Acceptance means queued or scheduled, not delivered. Without an `idempotency_key`, the SDK
        generates one and reuses it for automatic retries.
        """
        request = _send(
            from_=from_,
            to=to,
            subject=subject,
            html=html,
            text=text,
            from_name=from_name,
            cc=cc,
            bcc=bcc,
            reply_to=reply_to,
            template_id=template_id,
            template_variables=template_variables,
            metadata=metadata,
            scheduled_at=scheduled_at,
            idempotency_key=idempotency_key,
        )

        return cast(
            "SendEmailResponse",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    async def cancel(
        self,
        message_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> CancelEmailResponse:
        """Cancels every scheduled delivery of a message. Canceling twice returns the same result."""
        request = _cancel(message_id)

        return cast(
            "CancelEmailResponse",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    async def reschedule(
        self,
        message_id: str,
        *,
        scheduled_at: dt.datetime | str,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> RescheduleEmailResponse:
        """Moves every scheduled delivery of a message to a new send time."""
        request = _reschedule(message_id, scheduled_at)

        return cast(
            "RescheduleEmailResponse",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    async def list(
        self,
        *,
        limit: int | None = None,
        cursor: str | None = None,
        status: EmailStatus | None = None,
        source: EmailSource | None = None,
        recipient: str | None = None,
        search: str | None = None,
        contact_id: str | None = None,
        template_id: str | None = None,
        start_date: dt.date | str | None = None,
        end_date: dt.date | str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> ListEmailsResponse:
        """Lists recipient deliveries, newest first. Pass `nextCursor` as `cursor` for the next page."""
        request = _list(
            limit=limit,
            cursor=cursor,
            status=status,
            source=source,
            recipient=recipient,
            search=search,
            contact_id=contact_id,
            template_id=template_id,
            start_date=start_date,
            end_date=end_date,
        )

        return cast(
            "ListEmailsResponse",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    async def get(
        self,
        delivery_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Email:
        """Fetches one recipient delivery, with its content and history, by delivery ID.

        Takes a delivery ID from `deliveryIds` or `list()`, not a message ID.
        """
        request = _get(delivery_id)

        return cast(
            "Email",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )
