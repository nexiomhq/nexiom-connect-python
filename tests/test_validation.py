from __future__ import annotations

import datetime as dt
import math
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from nexiom_connect import AsyncNexiomConnect, NexiomConnect, NexiomValidationError

from .conftest import API_KEY, FakeApi

if TYPE_CHECKING:
    from collections.abc import Callable


def test_api_key_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(NexiomValidationError, match="NEXIOM_API_KEY"):
        NexiomConnect()

    with pytest.raises(NexiomValidationError, match="NEXIOM_API_KEY"):
        AsyncNexiomConnect()

    monkeypatch.setenv("NEXIOM_API_KEY", "nc_from_environment")

    assert NexiomConnect().base_url == "https://api-connect.nxiom.com/api"


@pytest.mark.parametrize(
    "options",
    [
        {"api_key": ""},
        {"api_key": "nc key"},
        {"api_key": "nc_key\n"},
        {"api_key": "nc_é"},
        {"api_key": 123},
        {"base_url": ""},
        {"base_url": "/api"},
        {"base_url": "ftp://api.example.test"},
        {"base_url": "https://user:pass@api.example.test"},
        {"base_url": "https://api.example.test/api?x=1"},
        {"base_url": "https://api.example.test/api#top"},
        {"base_url": "https://api.example.test/ api"},
        {"base_url": "http://api.example.test"},
        {"base_url": "http://[::1"},
        {"timeout": 0},
        {"timeout": -1},
        {"timeout": math.inf},
        {"timeout": math.nan},
        {"timeout": True},
        {"timeout": "30"},
        {"max_retries": -1},
        {"max_retries": 11},
        {"max_retries": 1.5},
        {"max_retries": True},
    ],
)
def test_invalid_configuration(options: dict[str, Any]) -> None:
    api_key = options.pop("api_key", API_KEY)

    with pytest.raises(NexiomValidationError):
        NexiomConnect(api_key, **options)

    with pytest.raises(NexiomValidationError):
        AsyncNexiomConnect(api_key, **options)


def test_loopback_hosts_may_use_http() -> None:
    for url in ("http://localhost:3000/api", "http://127.0.0.1/api", "http://[::1]:8080/api/"):
        assert NexiomConnect(API_KEY, base_url=url).base_url == url.rstrip("/")


def test_wrong_kind_of_http_client_is_refused() -> None:
    with pytest.raises(NexiomValidationError, match=r"httpx\.Client"):
        NexiomConnect(API_KEY, http_client=httpx.AsyncClient())  # type: ignore[arg-type]

    with pytest.raises(NexiomValidationError, match=r"httpx\.AsyncClient"):
        AsyncNexiomConnect(API_KEY, http_client=httpx.Client())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "options",
    [
        {"timeout": 0},
        {"timeout": math.nan},
        {"timeout": False},
        {"max_retries": 11},
        {"max_retries": "2"},
    ],
)
def test_invalid_request_options(api: FakeApi, options: dict[str, Any]) -> None:
    with pytest.raises(NexiomValidationError):
        api.call(lambda nexiom: nexiom.contacts.list(**options))

    assert api.calls == []


@pytest.mark.parametrize(
    "operation",
    [
        lambda nexiom: nexiom.emails.send(
            from_="a@example.com",
            to="b@example.com",
            subject="Hi",
            text="Hi",
            fromName="Acme",
        ),
        lambda nexiom: nexiom.contacts.list(org_id="org_1"),
        lambda nexiom: nexiom.contacts.create(email="a@example.com", project_id="prj_1"),
        lambda nexiom: nexiom.messaging.send(
            channel="whatsapp",
            from_="+213555000111",
            to="+213555123456",
            template={"id": "mtp_1"},
            senderId="was_1",
        ),
    ],
)
def test_unknown_keywords_are_refused(api: FakeApi, operation: Callable[[Any], Any]) -> None:
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        api.call(operation)

    assert api.calls == []


_MISSING = object()

_EMAIL: dict[str, Any] = {
    "from_": "hello@example.com",
    "to": "customer@example.com",
    "subject": "Welcome",
    "text": "Thanks for joining us.",
}


def _send(**changes: Any) -> Callable[[Any], Any]:
    params = {**_EMAIL, **changes}
    params = {key: value for key, value in params.items() if value is not _MISSING}

    return lambda nexiom: nexiom.emails.send(**params)


@pytest.mark.parametrize(
    ("operation", "message"),
    [
        # Resource IDs
        (lambda nexiom: nexiom.contacts.get(""), "id must be a non-empty string"),
        (lambda nexiom: nexiom.contacts.get("   "), "id must be a non-empty string"),
        (lambda nexiom: nexiom.contacts.get("."), "dot segment"),
        (lambda nexiom: nexiom.contacts.get(".."), "dot segment"),
        (lambda nexiom: nexiom.contacts.get(42), "id must be a non-empty string"),
        (lambda nexiom: nexiom.emails.cancel(""), "message_id"),
        (lambda nexiom: nexiom.emails.get(".."), "delivery_id"),
        (lambda nexiom: nexiom.templates.get(""), "template_id"),
        (lambda nexiom: nexiom.domains.verify(""), "domain_id"),
        (lambda nexiom: nexiom.messaging.get(""), "message_id"),
        # Recipients
        (_send(to=[]), "to must contain 1 to 100 addresses"),
        (_send(to=[f"u{i}@example.com" for i in range(101)]), "to must contain 1 to 100"),
        (_send(to=" "), "to must be a non-empty string"),
        (_send(to=["a@example.com", ""]), "to must be a non-empty string"),
        (_send(to=b"customer@example.com"), "to must be an address or a list"),
        (_send(to=None), "to must be an address or a list"),
        (_send(cc=[]), "cc must contain 1 to 100"),
        (_send(to=["a@example.com", "b@example.com"], cc="c@example.com"), "CC and BCC"),
        (_send(to=["a@example.com", "b@example.com"], bcc=["c@example.com"]), "CC and BCC"),
        # Content
        (_send(from_=""), "from_ must be a non-empty string"),
        (_send(subject=_MISSING), "subject must be a non-empty string"),
        (_send(text=_MISSING), "html, text, or template_id is required"),
        (_send(text=" ", html=""), "html, text, or template_id is required"),
        (_send(from_name=5), "from_name must be a string"),
        (_send(template_variables=["a"]), "template_variables must be a mapping"),
        (_send(metadata={1: "a"}), "metadata must be a mapping"),
        (_send(metadata={"items": {1, 2}}), "JSON serializable"),
        (_send(metadata={"value": math.nan}), "JSON serializable"),
        (_send(metadata={"text": "\ud800"}), "JSON serializable"),
        # Idempotency keys
        (_send(idempotency_key=""), "idempotency_key"),
        (_send(idempotency_key="has space"), "idempotency_key"),
        (_send(idempotency_key="café"), "idempotency_key"),
        (_send(idempotency_key="order-1\n"), "idempotency_key"),
        (_send(idempotency_key="k" * 129), "idempotency_key"),
        # Dates
        (_send(scheduled_at=dt.datetime(2026, 10, 20, 9)), "timezone-aware"),  # noqa: DTZ001
        (_send(scheduled_at="tomorrow"), "ISO 8601"),
        (_send(scheduled_at="2026-02-30T09:00:00Z"), "valid date"),
        (_send(scheduled_at="2026-10-20T25:00:00Z"), "valid date"),
        (_send(scheduled_at="2026-10-20T09:00:00+24:00"), "valid date"),
        (_send(scheduled_at="٢٠٢٦-10-20"), "ISO 8601"),
        (lambda nexiom: nexiom.emails.list(start_date="last week"), "start_date"),
        (lambda nexiom: nexiom.emails.list(end_date=20261020), "end_date"),
        (
            lambda nexiom: nexiom.emails.reschedule("msg_1", scheduled_at=""),
            "scheduled_at must be a non-empty string",
        ),
        # Integers and cursors
        (lambda nexiom: nexiom.emails.list(limit=0), "limit must be an integer between 1 and 100"),
        (lambda nexiom: nexiom.emails.list(limit=True), "limit must be an integer"),
        (lambda nexiom: nexiom.emails.list(limit=10.0), "limit must be an integer"),
        (lambda nexiom: nexiom.emails.list(limit="10"), "limit must be an integer"),
        (lambda nexiom: nexiom.emails.list(cursor="c" * 1025), "at most 1024"),
        (lambda nexiom: nexiom.contacts.list(page=10_001), "page must be an integer"),
        (lambda nexiom: nexiom.templates.list(page=0), "page must be an integer"),
        (lambda nexiom: nexiom.templates.versions("tpl_1", before_version=0), "before_version"),
        (lambda nexiom: nexiom.templates.versions("tpl_1", limit=101), "limit"),
        # Accepted values
        (lambda nexiom: nexiom.templates.list(status="live"), "status must be one of: draft"),
        (lambda nexiom: nexiom.templates.list(origin="mine"), "origin must be one of"),
        (lambda nexiom: nexiom.domains.list(status="active"), "status must be one of"),
        (lambda nexiom: nexiom.contacts.list(email_status="active"), "email_status must be one of"),
        (
            lambda nexiom: nexiom.contacts.update("ct_1", email="a@example.com", email_status="x"),
            "email_status must be one of",
        ),
        # Contacts
        (lambda nexiom: nexiom.contacts.create(email=""), "email must be a non-empty string"),
        (lambda nexiom: nexiom.contacts.update("ct_1", email=None), "email must be"),
        (
            lambda nexiom: nexiom.contacts.create(email="a@example.com", properties=[("a", 1)]),
            "properties must be a mapping",
        ),
        (lambda nexiom: nexiom.contacts.create(email="a@example.com", user_id=7), "user_id"),
        # Contact properties
        (lambda nexiom: nexiom.contacts.properties.create(name="", type="string"), "name"),
        (lambda nexiom: nexiom.contacts.properties.create(name="n" * 256, type="string"), "255"),
        (
            lambda nexiom: nexiom.contacts.properties.create(name="plan", type="text"),
            "type must be",
        ),
        (
            lambda nexiom: nexiom.contacts.properties.create(
                name="plan",
                type="string",
                fallback_value=5,
            ),
            "fallback_value",
        ),
        (
            lambda nexiom: nexiom.contacts.properties.create(
                name="plan",
                type="string",
                fallback_value="f" * 1001,
            ),
            "fallback_value",
        ),
        (
            lambda nexiom: nexiom.contacts.properties.update("prop_1"),
            "name, type, or fallback_value",
        ),
        # Suppressions
        (lambda nexiom: nexiom.emails.suppressions.list(search="  "), "search must contain"),
        (lambda nexiom: nexiom.emails.suppressions.list(search="s" * 256), "search must contain"),
        (lambda nexiom: nexiom.emails.suppressions.list(cursor=""), "cursor must contain"),
        (lambda nexiom: nexiom.emails.suppressions.list(cursor="c" * 401), "cursor must contain"),
        # Domains
        (lambda nexiom: nexiom.domains.create(domain=""), "domain must be a non-empty string"),
        (
            lambda nexiom: nexiom.domains.create(domain="mail.example.com", open_tracking="yes"),
            "open_tracking must be a boolean",
        ),
    ],
)
def test_invalid_arguments(api: FakeApi, operation: Callable[[Any], Any], message: str) -> None:
    with pytest.raises(NexiomValidationError, match=message):
        api.call(operation)

    assert api.calls == []
