from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nexiom_connect import ErrorKind, NexiomError

if TYPE_CHECKING:
    from .conftest import FakeApi

CONTACT = {"id": "ct_1", "email": "ada@example.com"}

PROPERTIES = [
    {"id": "prop_1", "key": "Company", "type": "string", "fallback_value": None},
    {"id": "prop_2", "key": "signup_date", "type": "date", "fallback_value": None},
    {"id": "prop_3", "key": "company_size", "type": "number", "fallback_value": "0"},
]


def test_contact_methods(api: FakeApi) -> None:
    api.ok(CONTACT, status=201)
    api.call(
        lambda nexiom: nexiom.contacts.create(
            email="ada@example.com",
            first_name="Ada",
            last_name=None,
            user_id=None,
            properties={"company": "Example", "seats": 3, "score": 9.5, "plan": None},
        ),
    )
    assert api.last.method == "POST"
    assert api.last.path == "/api/v1/emails/contacts"
    assert api.last.json == {
        "email": "ada@example.com",
        "firstName": "Ada",
        "properties": {"company": "Example", "seats": 3, "score": 9.5, "plan": None},
    }

    api.ok({"items": [], "total": 0, "page": 2, "limit": 25})
    api.call(
        lambda nexiom: nexiom.contacts.list(
            page=2,
            limit=25,
            search="ada",
            email_status="subscribed",
            segment_id="seg_1",
            list_id="lst_1",
        ),
    )
    assert api.last.query == {
        "page": "2",
        "limit": "25",
        "search": "ada",
        "emailStatus": "subscribed",
        "segmentId": "seg_1",
        "listId": "lst_1",
    }

    api.ok(CONTACT)
    api.call(lambda nexiom: nexiom.contacts.get("ct 1/2?"))
    assert api.last.path == "/api/v1/emails/contacts/ct%201%2F2%3F"

    api.ok(CONTACT)
    api.call(
        lambda nexiom: nexiom.contacts.update(
            "ct_1",
            email="ada@example.com",
            user_id=None,
            phone_number="+213555123456",
            email_status="unsubscribed",
        ),
    )
    assert api.last.method == "PUT"
    assert api.last.json == {
        "email": "ada@example.com",
        "userId": None,
        "phoneNumber": "+213555123456",
        "emailStatus": "unsubscribed",
    }

    api.ok(CONTACT)
    api.call(lambda nexiom: nexiom.contacts.update("ct_1", email="ada@example.com"))
    assert api.last.json == {"email": "ada@example.com"}

    api.reply(200, {"success": True})
    assert api.call(lambda nexiom: nexiom.contacts.delete("ct_1")) == {"success": True}
    assert api.last.method == "DELETE"


def test_property_methods(api: FakeApi) -> None:
    api.ok(PROPERTIES[0], status=201)
    api.call(lambda nexiom: nexiom.contacts.properties.create(name="Company", type="string"))
    assert api.last.path == "/api/v1/emails/properties"
    assert api.last.json == {"key": "Company", "type": "string"}

    api.ok(PROPERTIES[2], status=201)
    api.call(
        lambda nexiom: nexiom.contacts.properties.create(
            name="company_size",
            type="number",
            fallback_value=None,
        ),
    )
    assert api.last.json == {"key": "company_size", "type": "number", "fallback_value": None}

    api.ok(PROPERTIES[0])
    api.call(lambda nexiom: nexiom.contacts.properties.update("prop_1", fallback_value="Unknown"))
    assert api.last.method == "PATCH"
    assert api.last.path == "/api/v1/emails/properties/prop_1"
    assert api.last.json == {"fallback_value": "Unknown"}

    api.ok(PROPERTIES[0])
    api.call(lambda nexiom: nexiom.contacts.properties.update("prop_1", fallback_value=None))
    assert api.last.json == {"fallback_value": None}

    api.ok(PROPERTIES[0])
    api.call(lambda nexiom: nexiom.contacts.properties.update("prop_1", name="Org", type="string"))
    assert api.last.json == {"key": "Org", "type": "string"}

    api.reply(200, {"success": True})
    api.call(lambda nexiom: nexiom.contacts.properties.delete("prop_1"))
    assert api.last.method == "DELETE"


def test_property_list_filters_locally(api: FakeApi) -> None:
    api.ok(PROPERTIES)
    assert api.call(lambda nexiom: nexiom.contacts.properties.list()) == PROPERTIES
    assert api.last.query == {}

    api.ok(PROPERTIES)
    matches = api.call(lambda nexiom: nexiom.contacts.properties.list(search="COMPANY"))
    assert [item["id"] for item in matches] == ["prop_1", "prop_3"]

    api.ok(PROPERTIES)
    matches = api.call(
        lambda nexiom: nexiom.contacts.properties.list(type="number", search="company")
    )
    assert [item["id"] for item in matches] == ["prop_3"]


@pytest.mark.parametrize(
    "data",
    [{"key": "a"}, [{"id": "prop_1"}], [{"key": 5}], ["company"], [[]]],
)
def test_malformed_property_collections_are_protocol_errors(api: FakeApi, data: object) -> None:
    api.ok(data)

    with pytest.raises(NexiomError) as raised:
        api.call(lambda nexiom: nexiom.contacts.properties.list())

    assert raised.value.kind is ErrorKind.PROTOCOL
