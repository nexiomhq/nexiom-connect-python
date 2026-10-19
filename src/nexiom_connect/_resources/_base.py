from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .._transport import AsyncTransport, SyncTransport


class SyncResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport


class AsyncResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport
