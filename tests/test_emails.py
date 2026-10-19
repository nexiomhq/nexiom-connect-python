from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

import pytest

from nexiom_connect import ErrorKind, NexiomError

if TYPE_CHECKING:
    from .conftest import FakeApi

SENT = {"messageId": "msg_1", "deliveryIds": ["dlv_1"], "totalQueued": 1, "scheduledAt": None}


def test_send_maps_arguments_to_the_api(api: FakeApi) -> None:
    api.ok(SENT, status=202)

    result = api.call(
        lambda nexiom: nexiom.emails.send(
            from_="hello@example.com",
            from_name="Acme",
            to=("ada@example.com",),
            cc="cc@example.com",
            bcc=["bcc@example.com"],
            reply_to="support@example.com",
            subject="Welcome",
            html="<p>Hi</p>",
            text="Hi",
            metadata={},
            idempotency_key="order-123-confirmation",
        ),
    )

    assert result == SENT

    call = api.last
    assert call.method == "POST"
    assert call.path == "/api/v1/emails/send"
    assert call.headers["content-type"] == "application/json"
    assert call.headers["idempotency-key"] == "order-123-confirmation"
    assert call.json == {
        "from": "hello@example.com",
        "fromName": "Acme",
        "to": ["ada@example.com"],
        "cc": "cc@example.com",
        "bcc": ["bcc@example.com"],
        "replyTo": "support@example.com",
        "subject": "Welcome",
        "html": "<p>Hi</p>",
        "text": "Hi",
        "metadata": {},
    }


def test_template_sends_need_no_subject_or_body(api: FakeApi) -> None:
    api.ok(SENT, status=202)

    api.call(
        lambda nexiom: nexiom.emails.send(
            from_="hello@example.com",
            to="ada@example.com",
            template_id="tpl_1",
            template_variables={"first_name": "Ada", "count": 3, "vip": True},
        ),
    )

    assert api.last.json == {
        "from": "hello@example.com",
        "to": "ada@example.com",
        "templateId": "tpl_1",
        "templateVariables": {"first_name": "Ada", "count": 3, "vip": True},
    }


def test_text_is_sent_as_utf8(api: FakeApi) -> None:
    api.ok(SENT, status=202)

    api.call(
        lambda nexiom: nexiom.emails.send(
            from_="hello@example.com",
            to="amina@example.com",
            subject="مرحبا",
            text="Café 🎉",
        ),
    )

    assert "مرحبا".encode() in api.last.content
    assert api.last.json["text"] == "Café 🎉"


def test_dates_are_serialized(api: FakeApi) -> None:
    algiers = dt.timezone(dt.timedelta(hours=1))

    api.ok({**SENT, "scheduledAt": "2026-10-20T08:00:00.000Z"}, status=202)
    api.call(
        lambda nexiom: nexiom.emails.send(
            from_="hello@example.com",
            to="ada@example.com",
            subject="Later",
            text="Later",
            scheduled_at=dt.datetime(2026, 10, 20, 9, 0, tzinfo=algiers),
        ),
    )
    assert api.last.json["scheduledAt"] == "2026-10-20T08:00:00.000Z"

    api.ok({"messageId": "msg_1", "status": "scheduled", "scheduledAt": "x", "deliveryIds": []})
    api.call(
        lambda nexiom: nexiom.emails.reschedule("msg_1", scheduled_at="2026-10-21T09:00:00+01:00")
    )
    assert api.last.method == "PATCH"
    assert api.last.path == "/api/v1/emails/messages/msg_1"
    assert api.last.json == {"scheduledAt": "2026-10-21T09:00:00+01:00"}

    api.ok({"items": [], "total": None, "limit": 50, "hasMore": False, "nextCursor": None})
    api.call(
        lambda nexiom: nexiom.emails.list(
            start_date=dt.date(2026, 10, 1),
            end_date="2026-10-19T23:59:59.999Z",
        ),
    )
    assert api.last.query == {"startDate": "2026-10-01", "endDate": "2026-10-19T23:59:59.999Z"}


def test_list_sends_present_filters_only(api: FakeApi) -> None:
    page: dict[str, Any] = {
        "items": [],
        "total": None,
        "limit": 20,
        "hasMore": False,
        "nextCursor": None,
    }
    api.ok(page)

    result = api.call(
        lambda nexiom: nexiom.emails.list(
            limit=20,
            cursor="cur_1",
            status="bounced",
            source="api",
            recipient="ada@example.com",
            search="welcome",
            contact_id="ct_1",
            template_id=None,
        ),
    )

    assert result == page
    assert api.last.path == "/api/v1/emails/logs"
    assert api.last.query == {
        "limit": "20",
        "cursor": "cur_1",
        "status": "bounced",
        "source": "api",
        "recipient": "ada@example.com",
        "search": "welcome",
        "contactId": "ct_1",
    }


def test_cancel_and_delivery_reads_retry(api: FakeApi) -> None:
    canceled = {"messageId": "msg/1", "status": "canceled", "canceledAt": "t", "deliveryIds": []}
    api.reply(503, {"message": "Unavailable"})
    api.ok(canceled)

    assert api.call(lambda nexiom: nexiom.emails.cancel("msg/1")) == canceled
    assert api.last.method == "POST"
    assert api.last.path == "/api/v1/emails/messages/msg%2F1/cancel"
    assert api.last.content == b""
    assert len(api.calls) == 2

    delivery = {"id": "dlv_1", "status": "delivered"}
    api.reply(502, {"message": "Bad gateway"})
    api.reply(200, delivery)

    assert api.call(lambda nexiom: nexiom.emails.get("dlv_1")) == delivery
    assert api.last.path == "/api/v1/emails/logs/dlv_1"
    assert len(api.calls) == 4


@pytest.mark.parametrize("body", [b"[]", b'"dlv_1"', b"null"])
def test_delivery_detail_must_be_an_object(api: FakeApi, body: bytes) -> None:
    api.reply(200, body)

    with pytest.raises(NexiomError) as raised:
        api.call(lambda nexiom: nexiom.emails.get("dlv_1"))

    assert raised.value.kind is ErrorKind.PROTOCOL


def test_suppressions_are_listed(api: FakeApi) -> None:
    page: dict[str, Any] = {
        "items": [{"email": "a@example.com", "reason": "hard_bounce"}],
        "nextCursor": None,
        "hasMore": False,
    }
    api.ok(page)

    result = api.call(
        lambda nexiom: nexiom.emails.suppressions.list(
            search="  example.com ", limit=10, cursor="c1"
        ),
    )

    assert result == page
    assert api.last.path == "/api/v1/emails/suppressions"
    assert api.last.query == {"search": "example.com", "limit": "10", "cursor": "c1"}
