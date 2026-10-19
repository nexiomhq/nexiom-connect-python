"""Type-checked with `mypy --strict`, never run: how SDK users see the types."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from typing_extensions import assert_type

from nexiom_connect import AsyncNexiomConnect, ErrorKind, NexiomConnect, NexiomError, Webhooks
from nexiom_connect.types import (
    CancelEmailResponse,
    ContactDetails,
    ContactProperty,
    DeleteResponse,
    Domain,
    Email,
    ListContactsResponse,
    Message,
    MessageDetails,
    SendEmailResponse,
    TemplateVariable,
    WebhookEvent,
)


def sync_client(nexiom: NexiomConnect) -> None:
    sent = nexiom.emails.send(
        from_="hello@example.com",
        to=["ada@example.com"],
        subject="Welcome",
        text="Hi",
        scheduled_at=dt.datetime.now(dt.timezone.utc),
        timeout=10,
    )
    assert_type(sent, SendEmailResponse)
    assert_type(sent["messageId"], str)
    assert_type(sent["scheduledAt"], "str | None")

    assert_type(nexiom.emails.cancel(sent["messageId"]), CancelEmailResponse)
    assert_type(nexiom.emails.get(sent["deliveryIds"][0]), Email)

    page = nexiom.contacts.list(email_status="subscribed")
    assert_type(page, ListContactsResponse)
    assert_type(nexiom.contacts.get(page["items"][0]["id"]), ContactDetails)
    assert_type(nexiom.contacts.delete("ct_1"), DeleteResponse)
    nexiom.contacts.update("ct_1", email="ada@example.com", user_id=None)

    properties = nexiom.contacts.properties.list(type="number")
    assert_type(properties, list[ContactProperty])

    variables = nexiom.templates.variables("tpl_1")
    assert_type(variables, list[TemplateVariable])

    domain = nexiom.domains.verify("dom_1")
    assert_type(domain, Domain)
    records = domain.get("dns_records", [])
    assert_type(
        records[0]["status"],
        Literal["not_started", "pending", "verified", "failed", "temporary_failure"],
    )

    message = nexiom.messaging.send(
        channel="whatsapp",
        from_="+213555000111",
        to="+213555123456",
        template={"id": "mtp_1", "variables": {"body": {1: "Amina", "order": "A-1"}}},
    )
    assert_type(message, Message)
    assert_type(nexiom.messaging.get(message["id"]), MessageDetails)


async def async_client(nexiom: AsyncNexiomConnect) -> None:
    sent = await nexiom.emails.send(
        from_="a@example.com", to="b@example.com", subject="Hi", text="Hi"
    )
    assert_type(sent, SendEmailResponse)

    message = await nexiom.messaging.get("msg_1")
    assert_type(
        message["status"],
        Literal[
            "sending", "accepted", "sent", "delivered", "read", "failed", "uncertain", "received"
        ],
    )


def errors(nexiom: NexiomConnect) -> None:
    try:
        nexiom.contacts.get("ct_1")
    except NexiomError as error:
        assert_type(error.kind, ErrorKind)
        assert_type(error.status, "int | None")
        assert_type(error.code, "str | None")
        assert_type(error.response.idempotency_key, "str | None")


def webhooks(body: bytes, headers: dict[str, str]) -> str:
    event = Webhooks().construct_event(body, headers, "whsec_1")
    assert_type(event, WebhookEvent)

    if event["type"] == "email.scheduled":
        return event["data"]["scheduled_at"]

    if event["type"] == "whatsapp.message.failed":
        return event["data"]["failure_code"]

    if event["type"] == "whatsapp.message.received":
        return event["data"]["contact"]["name"] or event["data"]["sender"]

    if event["type"] == "contact.unsubscribed":
        return event["data"]["status"]

    return event["id"]
