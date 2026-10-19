"""Create, list, update, and delete contacts and their custom properties."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from .. import _validate as validate
from .._errors import NexiomValidationError
from .._transport import Request
from .._validate import NOT_GIVEN, NotGiven
from ._base import AsyncResource, SyncResource

if TYPE_CHECKING:
    import builtins
    from collections.abc import Mapping

    from .._transport import AsyncTransport, SyncTransport
    from ..types import (
        Contact,
        ContactDetails,
        ContactEmailStatus,
        ContactProperty,
        ContactPropertyType,
        ContactPropertyValue,
        DeleteResponse,
        ListContactsResponse,
    )

_PATH = "/v1/emails/contacts"

_PROPERTIES_PATH = "/v1/emails/properties"

# The API bounds page offsets; narrow larger collections with filters or search.
_MAX_PAGE = 10_000

_EMAIL_STATUSES = ("subscribed", "unsubscribed")

_PROPERTY_TYPES = ("string", "number", "date")


def _contact_body(
    *,
    email: object,
    user_id: object,
    first_name: object,
    last_name: object,
    phone_number: object,
    properties: object,
    email_status: object = None,
) -> dict[str, Any]:
    validate.non_empty(email, "email")

    for value, name in (
        (first_name, "first_name"),
        (last_name, "last_name"),
        (phone_number, "phone_number"),
    ):
        validate.optional_string(value, name)

    body: dict[str, Any] = {"email": email}

    # `None` clears the external user ID on update; leaving it out keeps it.
    if not isinstance(user_id, NotGiven):
        body["userId"] = validate.optional_string(user_id, "user_id")

    fields = {
        "firstName": first_name,
        "lastName": last_name,
        "phoneNumber": phone_number,
        "properties": validate.optional_map(properties, "properties"),
        "emailStatus": validate.optional_one_of(email_status, "email_status", _EMAIL_STATUSES),
    }

    body.update({key: value for key, value in fields.items() if value is not None})

    return body


def _create(
    *,
    email: object,
    user_id: object,
    first_name: object,
    last_name: object,
    phone_number: object,
    properties: object,
) -> Request:
    body = _contact_body(
        email=email,
        # On create, None leaves the external user ID out.
        user_id=NOT_GIVEN if user_id is None else user_id,
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        properties=properties,
    )

    return Request("POST", _PATH, body=body)


def _list(
    *,
    page: object,
    limit: object,
    search: object,
    email_status: object,
    segment_id: object,
    list_id: object,
) -> Request:
    query = validate.query(
        {
            "page": validate.optional_integer(page, "page", 1, _MAX_PAGE),
            "limit": validate.optional_integer(limit, "limit", 1, 100),
            "search": validate.optional_string(search, "search"),
            "emailStatus": validate.optional_one_of(email_status, "email_status", _EMAIL_STATUSES),
            "segmentId": validate.optional_string(segment_id, "segment_id"),
            "listId": validate.optional_string(list_id, "list_id"),
        },
    )

    return Request("GET", _PATH, query=query)


def _get(contact_id: object) -> Request:
    return Request("GET", f"{_PATH}/{validate.resource_id(contact_id)}")


def _update(
    contact_id: object,
    *,
    email: object,
    user_id: object,
    first_name: object,
    last_name: object,
    phone_number: object,
    properties: object,
    email_status: object,
) -> Request:
    path = f"{_PATH}/{validate.resource_id(contact_id)}"

    body = _contact_body(
        email=email,
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        properties=properties,
        email_status=email_status,
    )

    return Request("PUT", path, body=body)


def _delete(contact_id: object) -> Request:
    return Request("DELETE", f"{_PATH}/{validate.resource_id(contact_id)}")


def _property_name(value: object) -> str:
    name = validate.non_empty(value, "name")

    if len(name.strip()) > 255:
        raise NexiomValidationError("name must contain at most 255 characters")

    return name


def _property_type(value: object) -> str:
    if value not in _PROPERTY_TYPES:
        raise NexiomValidationError("type must be string, number, or date")

    return value


def _fallback(value: object) -> str | None:
    if value is not None and (not isinstance(value, str) or len(value) > 1000):
        raise NexiomValidationError(
            "fallback_value must be None or a string of at most 1000 characters"
        )

    return value


def _create_property(*, name: object, type_: object, fallback_value: object) -> Request:
    body: dict[str, Any] = {
        "key": _property_name(name),
        "type": _property_type(type_),
    }

    if not isinstance(fallback_value, NotGiven):
        body["fallback_value"] = _fallback(fallback_value)

    return Request("POST", _PROPERTIES_PATH, body=body)


def _list_properties(*, type_: object, search: object) -> Request:
    wanted = validate.optional_string(type_, "type")
    term = validate.optional_string(search, "search")
    needle = term.casefold() if term else None

    def matches(item: dict[str, Any]) -> bool:
        return (not wanted or item.get("type") == wanted) and (
            needle is None or needle in item["key"].casefold()
        )

    def transform(data: builtins.list[dict[str, Any]]) -> builtins.list[dict[str, Any]]:
        return [item for item in data if matches(item)]

    return Request(
        "GET",
        _PROPERTIES_PATH,
        accepts=_is_property_collection,
        transform=transform,
    )


def _update_property(
    property_id: object, *, name: object, type_: object, fallback_value: object
) -> Request:
    path = f"{_PROPERTIES_PATH}/{validate.resource_id(property_id)}"

    if name is None and type_ is None and isinstance(fallback_value, NotGiven):
        raise NexiomValidationError("name, type, or fallback_value is required")

    body: dict[str, Any] = {}

    if name is not None:
        body["key"] = _property_name(name)

    if type_ is not None:
        body["type"] = _property_type(type_)

    if not isinstance(fallback_value, NotGiven):
        body["fallback_value"] = _fallback(fallback_value)

    return Request("PATCH", path, body=body)


def _delete_property(property_id: object) -> Request:
    return Request("DELETE", f"{_PROPERTIES_PATH}/{validate.resource_id(property_id)}")


def _is_property_collection(data: object) -> bool:
    return isinstance(data, list) and all(
        isinstance(item, dict) and isinstance(item.get("key"), str) for item in data
    )


class ContactProperties(SyncResource):
    """Manage the custom properties stored on contacts."""

    def create(
        self,
        *,
        name: str,
        type: ContactPropertyType,
        fallback_value: str | NotGiven | None = NOT_GIVEN,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> ContactProperty:
        """Creates a property. The API stores fallback values as strings, including numbers and dates."""
        request = _create_property(name=name, type_=type, fallback_value=fallback_value)

        return cast(
            "ContactProperty",
            self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    def list(
        self,
        *,
        type: ContactPropertyType | None = None,
        search: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> builtins.list[ContactProperty]:
        """Lists properties.

        The optional `type` and case-insensitive `search` filters are applied locally to the
        complete collection.
        """
        request = _list_properties(type_=type, search=search)

        return cast(
            "builtins.list[ContactProperty]",
            self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    def update(
        self,
        property_id: str,
        *,
        name: str | None = None,
        type: ContactPropertyType | None = None,
        fallback_value: str | NotGiven | None = NOT_GIVEN,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> ContactProperty:
        """Renames a property, changes its type, or sets its fallback. Give at least one.

        A type can change only while no contact has a value for the property. `fallback_value=None`
        clears the fallback.
        """
        request = _update_property(
            property_id, name=name, type_=type, fallback_value=fallback_value
        )

        return cast(
            "ContactProperty",
            self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    def delete(
        self,
        property_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> DeleteResponse:
        """Deletes a property."""
        request = _delete_property(property_id)

        return cast(
            "DeleteResponse",
            self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )


class AsyncContactProperties(AsyncResource):
    """Manage the custom properties stored on contacts."""

    async def create(
        self,
        *,
        name: str,
        type: ContactPropertyType,
        fallback_value: str | NotGiven | None = NOT_GIVEN,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> ContactProperty:
        """Creates a property. The API stores fallback values as strings, including numbers and dates."""
        request = _create_property(name=name, type_=type, fallback_value=fallback_value)

        return cast(
            "ContactProperty",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    async def list(
        self,
        *,
        type: ContactPropertyType | None = None,
        search: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> builtins.list[ContactProperty]:
        """Lists properties.

        The optional `type` and case-insensitive `search` filters are applied locally to the
        complete collection.
        """
        request = _list_properties(type_=type, search=search)

        return cast(
            "builtins.list[ContactProperty]",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    async def update(
        self,
        property_id: str,
        *,
        name: str | None = None,
        type: ContactPropertyType | None = None,
        fallback_value: str | NotGiven | None = NOT_GIVEN,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> ContactProperty:
        """Renames a property, changes its type, or sets its fallback. Give at least one.

        A type can change only while no contact has a value for the property. `fallback_value=None`
        clears the fallback.
        """
        request = _update_property(
            property_id, name=name, type_=type, fallback_value=fallback_value
        )

        return cast(
            "ContactProperty",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    async def delete(
        self,
        property_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> DeleteResponse:
        """Deletes a property."""
        request = _delete_property(property_id)

        return cast(
            "DeleteResponse",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )


class Contacts(SyncResource):
    """Create, list, update, and delete contacts."""

    def __init__(self, transport: SyncTransport) -> None:
        super().__init__(transport)

        self.properties = ContactProperties(transport)

    def create(
        self,
        *,
        email: str,
        user_id: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        phone_number: str | None = None,
        properties: Mapping[str, ContactPropertyValue] | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Contact:
        """Creates a contact."""
        request = _create(
            email=email,
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            properties=properties,
        )

        return cast(
            "Contact", self._transport.request(request, timeout=timeout, max_retries=max_retries)
        )

    def list(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
        search: str | None = None,
        email_status: ContactEmailStatus | None = None,
        segment_id: str | None = None,
        list_id: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> ListContactsResponse:
        """Lists or searches contacts, 50 per page by default and at most 100."""
        request = _list(
            page=page,
            limit=limit,
            search=search,
            email_status=email_status,
            segment_id=segment_id,
            list_id=list_id,
        )

        return cast(
            "ListContactsResponse",
            self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    def get(
        self,
        contact_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> ContactDetails:
        """Gets a contact with its properties and activity."""
        request = _get(contact_id)

        return cast(
            "ContactDetails",
            self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    def update(
        self,
        contact_id: str,
        *,
        email: str,
        user_id: str | NotGiven | None = NOT_GIVEN,
        first_name: str | None = None,
        last_name: str | None = None,
        phone_number: str | None = None,
        properties: Mapping[str, ContactPropertyValue] | None = None,
        email_status: ContactEmailStatus | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Contact:
        """Updates a contact. The API requires `email`; `user_id=None` clears the external user ID."""
        request = _update(
            contact_id,
            email=email,
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            properties=properties,
            email_status=email_status,
        )

        return cast(
            "Contact", self._transport.request(request, timeout=timeout, max_retries=max_retries)
        )

    def delete(
        self,
        contact_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> DeleteResponse:
        """Deletes a contact."""
        request = _delete(contact_id)

        return cast(
            "DeleteResponse",
            self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )


class AsyncContacts(AsyncResource):
    """Create, list, update, and delete contacts."""

    def __init__(self, transport: AsyncTransport) -> None:
        super().__init__(transport)

        self.properties = AsyncContactProperties(transport)

    async def create(
        self,
        *,
        email: str,
        user_id: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        phone_number: str | None = None,
        properties: Mapping[str, ContactPropertyValue] | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Contact:
        """Creates a contact."""
        request = _create(
            email=email,
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            properties=properties,
        )

        return cast(
            "Contact",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    async def list(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
        search: str | None = None,
        email_status: ContactEmailStatus | None = None,
        segment_id: str | None = None,
        list_id: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> ListContactsResponse:
        """Lists or searches contacts, 50 per page by default and at most 100."""
        request = _list(
            page=page,
            limit=limit,
            search=search,
            email_status=email_status,
            segment_id=segment_id,
            list_id=list_id,
        )

        return cast(
            "ListContactsResponse",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    async def get(
        self,
        contact_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> ContactDetails:
        """Gets a contact with its properties and activity."""
        request = _get(contact_id)

        return cast(
            "ContactDetails",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    async def update(
        self,
        contact_id: str,
        *,
        email: str,
        user_id: str | NotGiven | None = NOT_GIVEN,
        first_name: str | None = None,
        last_name: str | None = None,
        phone_number: str | None = None,
        properties: Mapping[str, ContactPropertyValue] | None = None,
        email_status: ContactEmailStatus | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Contact:
        """Updates a contact. The API requires `email`; `user_id=None` clears the external user ID."""
        request = _update(
            contact_id,
            email=email,
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            properties=properties,
            email_status=email_status,
        )

        return cast(
            "Contact",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    async def delete(
        self,
        contact_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> DeleteResponse:
        """Deletes a contact."""
        request = _delete(contact_id)

        return cast(
            "DeleteResponse",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )
