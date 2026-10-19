from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import pytest

from nexiom_connect import ErrorKind, NexiomError, NexiomValidationError

from .conftest import FakeApi, message

if TYPE_CHECKING:
    from collections.abc import Callable

RETRY_STATUSES = [408, 429, 500, 502, 503, 504]


def _send(**changes: Any) -> Callable[[Any], Any]:
    params: dict[str, Any] = {
        "channel": "whatsapp",
        "from_": "+213555000111",
        "to": "+213555123456",
        "template": {"id": "mtp_1"},
        **changes,
    }

    return lambda nexiom: nexiom.messaging.send(**params)


def test_send_posts_the_template_with_an_idempotency_key(api: FakeApi) -> None:
    api.ok(message(), status=201)

    result = api.call(
        _send(
            from_=" +213555000111 ",
            template={
                "id": "mtp_1",
                "variables": {"header": {}, "body": {1: "Amina", "order": "A-1234"}},
            },
        ),
    )

    assert result == message()

    call = api.last
    assert call.method == "POST"
    assert call.path == "/api/v1/messaging/messages"
    assert re.fullmatch(r"[0-9a-f]{32}", call.headers["idempotency-key"])
    assert call.json == {
        "channel": "whatsapp",
        "from": "+213555000111",
        "to": "+213555123456",
        "template": {
            "id": "mtp_1",
            "variables": {"header": {}, "body": {"1": "Amina", "order": "A-1234"}},
        },
    }

    api.ok(message(), status=201)
    api.call(_send(template={"id": "mtp_1", "variables": {}}, idempotency_key="k" * 200))
    assert api.last.headers["idempotency-key"] == "k" * 200
    assert api.last.json["template"] == {"id": "mtp_1", "variables": {}}

    api.ok(message(), status=201)
    api.call(_send(template={"id": "mtp_1", "variables": None}))
    assert api.last.json["template"] == {"id": "mtp_1"}


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"channel": "sms"}, "channel must be one of: whatsapp"),
        ({"channel": None}, "channel must be one of"),
        ({"from_": "0555000111"}, "from_ must be an E.164"),
        ({"from_": "was_1"}, "from_ must be an E.164"),
        ({"to": "+0213555123456"}, "to must be an E.164"),
        ({"to": "+٢١٣555123456"}, "to must be an E.164"),
        ({"to": None}, "to must be an E.164"),
        ({"template": None}, "template must be a mapping"),
        ({"template": ["mtp_1"]}, "template must be a mapping"),
        ({"template": {}}, "template.id must be a non-empty string"),
        ({"template": {"id": "mtp_1", "templateId": "x"}}, "Unknown template key 'templateId'"),
        ({"template": {"id": "mtp_1", "variables": [["1", "a"]]}}, "template.variables must be"),
        (
            {"template": {"id": "mtp_1", "variables": {"footer": {}}}},
            "Unknown template.variables key 'footer'",
        ),
        (
            {"template": {"id": "mtp_1", "variables": {"body": ["Amina"]}}},
            "template.variables.body must be a mapping",
        ),
        (
            {"template": {"id": "mtp_1", "variables": {"body": {"first name": "Amina"}}}},
            "keys must be variable numbers or names",
        ),
        (
            {"template": {"id": "mtp_1", "variables": {"body": {"first_name\n": "Amina"}}}},
            "keys must be variable numbers or names",
        ),
        (
            {"template": {"id": "mtp_1", "variables": {"body": {True: "Amina"}}}},
            "keys must be variable numbers or names",
        ),
        (
            {"template": {"id": "mtp_1", "variables": {"body": {"1": 5}}}},
            "template.variables.body.1 must be a string",
        ),
        (
            {"template": {"id": "mtp_1", "variables": {"header": {"1": "x" * 1025}}}},
            "at most 1024 characters",
        ),
        ({"idempotency_key": "k" * 201}, "idempotency_key"),
        ({"idempotency_key": "two words"}, "idempotency_key"),
    ],
)
def test_invalid_arguments_fail_before_any_request(
    api: FakeApi,
    changes: dict[str, Any],
    error: str,
) -> None:
    with pytest.raises(NexiomValidationError, match=re.escape(error)):
        api.call(_send(**changes))

    assert api.calls == []


@pytest.mark.parametrize("status", RETRY_STATUSES)
def test_sends_and_reads_retry_transient_failures(api: FakeApi, status: int) -> None:
    api.reply(status, {"message": "Try again"})
    api.ok(message(), status=201)

    api.call(_send())

    first, second = api.calls
    assert first.headers["idempotency-key"] == second.headers["idempotency-key"]
    assert first.content == second.content

    api.reply(status, {"message": "Try again"})
    api.ok(message(content=None, chat=None))

    assert api.call(lambda nexiom: nexiom.messaging.get("msg_1"))["id"] == "msg_1"
    assert api.last.path == "/api/v1/messaging/messages/msg_1"
    assert len(api.calls) == 4


@pytest.mark.parametrize(
    ("status", "code"),
    [(409, "idempotency_key_reused"), (422, "whatsapp_template_not_approved")],
)
def test_api_refusals_are_not_retried(api: FakeApi, status: int, code: str) -> None:
    api.reply(status, {"error": "unprocessable", "code": code, "message": "Refused"})

    with pytest.raises(NexiomError) as raised:
        api.call(_send(), max_retries=5)

    assert raised.value.status == status
    assert raised.value.code == code
    assert len(api.calls) == 1


@pytest.mark.parametrize(
    "data",
    [{"id": "msg_1"}, {"id": 1, "channel": "whatsapp"}, {"id": "msg_1", "channel": "sms"}, []],
)
def test_malformed_messages_are_protocol_errors(api: FakeApi, data: object) -> None:
    api.ok(data, status=201)

    with pytest.raises(NexiomError) as raised:
        api.call(_send())

    assert raised.value.kind is ErrorKind.PROTOCOL

    api.ok(data)

    with pytest.raises(NexiomError) as raised:
        api.call(lambda nexiom: nexiom.messaging.get("msg_1"))

    assert raised.value.kind is ErrorKind.PROTOCOL
