from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .conftest import FakeApi

DOMAIN = {"id": "dom_1", "domain": "mail.example.com", "status": "pending", "dns_records": []}


def test_domain_methods(api: FakeApi) -> None:
    api.ok(DOMAIN, status=201)
    assert api.call(lambda nexiom: nexiom.domains.create(domain="mail.example.com")) == DOMAIN
    assert api.last.method == "POST"
    assert api.last.path == "/api/v1/emails/domains"
    assert api.last.json == {"domain": "mail.example.com"}

    api.ok(DOMAIN, status=201)
    api.call(lambda nexiom: nexiom.domains.create(domain="mail.example.com", open_tracking=False))
    assert api.last.json == {"domain": "mail.example.com", "openTracking": False}

    api.ok({"items": [DOMAIN], "total": 1, "page": 1, "limit": 50})
    api.call(lambda nexiom: nexiom.domains.list(page=1, limit=50, status="pending", search="mail"))
    assert api.last.query == {"page": "1", "limit": "50", "status": "pending", "search": "mail"}

    api.ok(DOMAIN)
    api.call(lambda nexiom: nexiom.domains.get("dom_1"))
    assert api.last.path == "/api/v1/emails/domains/dom_1"

    api.reply(200, {"success": True})
    api.call(lambda nexiom: nexiom.domains.delete("dom_1"))
    assert api.last.method == "DELETE"


def test_verify_retries(api: FakeApi) -> None:
    verified = {**DOMAIN, "status": "verified"}
    api.reply(500, {"message": "Internal error"})
    api.reply(504, {"message": "Gateway timeout"})
    api.ok(verified)

    assert api.call(lambda nexiom: nexiom.domains.verify("dom_1")) == verified
    assert [call.path for call in api.calls] == ["/api/v1/emails/domains/dom_1/verify"] * 3
    assert all(call.method == "POST" for call in api.calls)
