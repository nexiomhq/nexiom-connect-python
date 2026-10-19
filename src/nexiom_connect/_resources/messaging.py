"""Send messages on any messaging channel, and read them back."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Final, Literal, cast

from .. import _validate as validate
from .._errors import NexiomValidationError
from .._transport import Request
from ._base import AsyncResource, SyncResource

if TYPE_CHECKING:
    from ..types import Message, MessageDetails, WhatsAppTemplate

_PATH = "/v1/messaging/messages"

# Messaging channels. New channels are added here, with their own parameters.
_CHANNELS = ("whatsapp",)

_TEMPLATE_KEYS = ("id", "variables")

_VARIABLE_GROUPS = ("header", "body")

_MAX_MESSAGE_IDEMPOTENCY_KEY = 200

_E164: Final = re.compile(r"\+[1-9][0-9]{6,14}", re.ASCII)

_VARIABLE_KEY: Final = re.compile(r"[A-Za-z0-9_]{1,64}", re.ASCII)


def _send(
    *,
    channel: object,
    from_: object,
    to: object,
    template: object,
    idempotency_key: object,
) -> Request:
    if channel not in _CHANNELS:
        raise NexiomValidationError(f"channel must be one of: {', '.join(_CHANNELS)}")

    if not isinstance(template, Mapping):
        raise NexiomValidationError("template must be a mapping with an id and variables")

    _known_keys(template, _TEMPLATE_KEYS, "template")

    body: dict[str, Any] = {
        "channel": channel,
        "from": _phone_number(from_, "from_"),
        "to": _phone_number(to, "to"),
        "template": {
            "id": validate.non_empty(template.get("id"), "template.id"),
        },
    }

    variables = template.get("variables")

    if variables is not None:
        if not isinstance(variables, Mapping):
            raise NexiomValidationError(
                "template.variables must be a mapping with header and body values"
            )

        _known_keys(variables, _VARIABLE_GROUPS, "template.variables")

        body["template"]["variables"] = {
            group: _values(variables[group], f"template.variables.{group}")
            for group in _VARIABLE_GROUPS
            if variables.get(group) is not None
        }

    key = validate.idempotency_key(idempotency_key, _MAX_MESSAGE_IDEMPOTENCY_KEY)

    return Request("POST", _PATH, body=body, idempotency_key=key, accepts=_is_message)


def _get(message_id: object) -> Request:
    path = f"{_PATH}/{validate.resource_id(message_id, 'message_id')}"

    return Request("GET", path, accepts=_is_message)


def _known_keys(values: Mapping[Any, Any], allowed: tuple[str, ...], name: str) -> None:
    """Refuses keys the API does not accept, so typos fail loudly instead of being dropped."""
    for key in values:
        if key not in allowed:
            raise NexiomValidationError(
                f"Unknown {name} key {key!r}. Accepted keys: {', '.join(allowed)}",
            )


def _phone_number(value: object, name: str) -> str:
    number = value.strip() if isinstance(value, str) else None

    if number is None or _E164.fullmatch(number) is None:
        raise NexiomValidationError(f"{name} must be an E.164 phone number, such as +213555123456")

    return number


def _values(value: object, name: str) -> dict[str, str]:
    """Variable values keyed by number or name. Integer keys (`{1: "Amina"}`) are sent as text."""
    if not isinstance(value, Mapping):
        raise NexiomValidationError(f"{name} must be a mapping keyed by variable number or name")

    values: dict[str, str] = {}

    for raw_key, item in value.items():
        if isinstance(raw_key, bool) or not isinstance(raw_key, (str, int)):
            raise NexiomValidationError(f"{name} keys must be variable numbers or names")

        key = str(raw_key)

        if _VARIABLE_KEY.fullmatch(key) is None:
            raise NexiomValidationError(f"{name} keys must be variable numbers or names")

        if not isinstance(item, str) or len(item) > 1024:
            raise NexiomValidationError(f"{name}.{key} must be a string of at most 1024 characters")

        values[key] = item

    return values


def _is_message(data: object) -> bool:
    return (
        isinstance(data, dict)
        and isinstance(data.get("id"), str)
        and data.get("channel") in _CHANNELS
    )


class Messaging(SyncResource):
    """Send messages on any messaging channel, such as WhatsApp, and read them back."""

    def send(
        self,
        *,
        channel: Literal["whatsapp"],
        from_: str,
        to: str,
        template: WhatsAppTemplate,
        idempotency_key: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Message:
        """Sends a message on the channel named by `channel`.

        WhatsApp sends an approved template from a connected number, named by its phone number in
        `from_`. Acceptance by WhatsApp is not delivery: follow the message with `get()` or
        webhooks. Without an `idempotency_key`, the SDK generates one and reuses it for automatic
        retries, so a message is sent at most once.
        """
        request = _send(
            channel=channel,
            from_=from_,
            to=to,
            template=template,
            idempotency_key=idempotency_key,
        )

        return cast(
            "Message", self._transport.request(request, timeout=timeout, max_retries=max_retries)
        )

    def get(
        self,
        message_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> MessageDetails:
        """Fetches one message with its current status, cost, and the content the recipient received."""
        request = _get(message_id)

        return cast(
            "MessageDetails",
            self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )


class AsyncMessaging(AsyncResource):
    """Send messages on any messaging channel, such as WhatsApp, and read them back."""

    async def send(
        self,
        *,
        channel: Literal["whatsapp"],
        from_: str,
        to: str,
        template: WhatsAppTemplate,
        idempotency_key: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Message:
        """Sends a message on the channel named by `channel`.

        WhatsApp sends an approved template from a connected number, named by its phone number in
        `from_`. Acceptance by WhatsApp is not delivery: follow the message with `get()` or
        webhooks. Without an `idempotency_key`, the SDK generates one and reuses it for automatic
        retries, so a message is sent at most once.
        """
        request = _send(
            channel=channel,
            from_=from_,
            to=to,
            template=template,
            idempotency_key=idempotency_key,
        )

        return cast(
            "Message",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )

    async def get(
        self,
        message_id: str,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> MessageDetails:
        """Fetches one message with its current status, cost, and the content the recipient received."""
        request = _get(message_id)

        return cast(
            "MessageDetails",
            await self._transport.request(request, timeout=timeout, max_retries=max_retries),
        )
