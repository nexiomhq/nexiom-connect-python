"""Shared argument validation. Every failure raises before a request is made."""

from __future__ import annotations

import datetime as dt
import re
import secrets
from collections.abc import Mapping, Sequence
from typing import Any, Final, final
from urllib.parse import quote

from ._errors import NexiomValidationError


@final
class NotGiven:
    """The default of an argument where `None` has a meaning of its own, such as clearing a value.

    Leave the argument out instead of passing this.
    """

    _instance: NotGiven | None = None

    def __new__(cls) -> NotGiven:
        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "NOT_GIVEN"

    def __reduce__(self) -> str:
        return "NOT_GIVEN"


NOT_GIVEN: Final = NotGiven()

# Patterns use fullmatch(): "$" also matches before a trailing newline. re.ASCII keeps \d and \s ASCII.
_ISO_8601: Final = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})"
    r"(?:T([0-9]{2}):([0-9]{2})(?::([0-9]{2})(?:\.[0-9]{1,9})?)?(Z|[+-][0-9]{2}:?[0-9]{2})?)?",
    re.ASCII | re.IGNORECASE,
)

_PRINTABLE_ASCII: Final = re.compile(r"[\x21-\x7e]+", re.ASCII)


def non_empty(value: object, name: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise NexiomValidationError(f"{name} must be a non-empty string")

    return value


def optional_string(value: object, name: str) -> str | None:
    """Returns the string, or `None` when the value is absent."""
    if value is not None and not isinstance(value, str):
        raise NexiomValidationError(f"{name} must be a string")

    return value


def optional_one_of(value: object, name: str, allowed: Sequence[str]) -> str | None:
    """Returns the value when it is one of `allowed`, or `None` when it is absent."""
    if value is None:
        return None

    if not isinstance(value, str) or value not in allowed:
        raise NexiomValidationError(f"{name} must be one of: {', '.join(allowed)}")

    return value


def integer(value: object, name: str, minimum: int, maximum: int | None = None) -> int:
    # bool is an int subclass; True is not a page number.
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < minimum
        or (maximum is not None and value > maximum)
    ):
        bounds = (
            f"between {minimum} and {maximum}" if maximum is not None else f"of at least {minimum}"
        )
        raise NexiomValidationError(f"{name} must be an integer {bounds}")

    return value


def optional_integer(
    value: object, name: str, minimum: int, maximum: int | None = None
) -> int | None:
    return None if value is None else integer(value, name, minimum, maximum)


def resource_id(value: object, name: str = "id") -> str:
    """Encodes an ID as one URL path segment."""
    identifier = non_empty(value, name)

    # URL parsers normalize dot segments, even when percent encoded.
    if identifier in {".", ".."}:
        raise NexiomValidationError(f"{name} cannot be a dot segment")

    return quote(identifier, safe="")


def timestamp(value: object, name: str) -> str:
    """Serializes a date, an aware datetime, or an ISO 8601 timestamp.

    The API checks the offset and the allowed range.
    """
    if isinstance(value, dt.datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise NexiomValidationError(
                f"{name} must be a timezone-aware datetime, such as datetime.now(timezone.utc)",
            )

        utc = value.astimezone(dt.timezone.utc)

        return utc.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    if isinstance(value, dt.date):
        return value.isoformat()

    text = non_empty(value, name)
    match = _ISO_8601.fullmatch(text)

    if match is None:
        raise NexiomValidationError(f"{name} must be a datetime, a date, or an ISO 8601 timestamp")

    year, month, day, hour, minute, second, offset = match.groups()

    try:
        dt.datetime(  # noqa: DTZ001 - only checks that the calendar fields exist.
            int(year),
            int(month),
            int(day),
            int(hour or 0),
            int(minute or 0),
            int(second or 0),
        )

        if offset is not None and offset.upper() != "Z":
            hours, minutes = int(offset[1:3]), int(offset[-2:])
            dt.timezone(dt.timedelta(hours=hours, minutes=minutes))

            if minutes > 59:
                raise ValueError(offset)
    except ValueError:
        raise NexiomValidationError(f"{name} must be a valid date") from None

    return text


def optional_timestamp(value: object, name: str) -> str | None:
    return None if value is None else timestamp(value, name)


def optional_map(value: object, name: str) -> dict[str, Any] | None:
    """Copies a mapping keyed by name, so it is always sent as a JSON object."""
    if value is None:
        return None

    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise NexiomValidationError(f"{name} must be a mapping keyed by name")

    return dict(value)


def idempotency_key(value: object, maximum: int) -> str:
    """Returns the caller's key, or a new random one when it is absent."""
    if value is None:
        return secrets.token_hex(16)

    if (
        not isinstance(value, str)
        or len(value) > maximum
        or _PRINTABLE_ASCII.fullmatch(value) is None
    ):
        raise NexiomValidationError(
            f"idempotency_key must be 1 to {maximum} printable ASCII characters without whitespace",
        )

    return value


def query(values: Mapping[str, str | int | None]) -> dict[str, str | int]:
    """Keeps the present values only."""
    return {key: value for key, value in values.items() if value is not None}


def is_list_of_objects(data: object) -> bool:
    return isinstance(data, list) and all(isinstance(item, dict) for item in data)
