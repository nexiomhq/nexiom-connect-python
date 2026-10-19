from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nexiom_connect import ErrorKind, NexiomError

if TYPE_CHECKING:
    from .conftest import FakeApi

VARIABLE = {
    "id": "var_1",
    "key": "first_name",
    "type": "string",
    "required": True,
    "fallback_value": None,
}


def test_template_methods(api: FakeApi) -> None:
    page = {"items": [], "total": 0, "page": 1, "limit": 50}
    api.ok(page)
    result = api.call(
        lambda nexiom: nexiom.templates.list(
            page=1,
            limit=50,
            status="changes_in_draft",
            search="welcome",
            origin="custom",
            category="onboarding",
        ),
    )
    assert result == page
    assert api.last.path == "/api/v1/emails/templates"
    assert api.last.query == {
        "page": "1",
        "limit": "50",
        "status": "changes_in_draft",
        "search": "welcome",
        "origin": "custom",
        "category": "onboarding",
    }

    api.ok({"id": "tpl_1", "published_version": None})
    api.call(lambda nexiom: nexiom.templates.get("tpl_1"))
    assert api.last.path == "/api/v1/emails/templates/tpl_1"

    api.ok([VARIABLE])
    assert api.call(lambda nexiom: nexiom.templates.variables("tpl_1")) == [VARIABLE]
    assert api.last.path == "/api/v1/emails/templates/tpl_1/variables"

    api.ok([])
    api.call(lambda nexiom: nexiom.templates.versions("tpl_1", limit=10, before_version=4))
    assert api.last.path == "/api/v1/emails/templates/tpl_1/versions"
    assert api.last.query == {"limit": "10", "beforeVersion": "4"}


@pytest.mark.parametrize("data", [{"items": []}, ["first_name"], [None]])
def test_malformed_lists_are_protocol_errors(api: FakeApi, data: object) -> None:
    api.ok(data)

    with pytest.raises(NexiomError) as raised:
        api.call(lambda nexiom: nexiom.templates.variables("tpl_1"))

    assert raised.value.kind is ErrorKind.PROTOCOL

    api.ok(data)

    with pytest.raises(NexiomError) as raised:
        api.call(lambda nexiom: nexiom.templates.versions("tpl_1"))

    assert raised.value.kind is ErrorKind.PROTOCOL
