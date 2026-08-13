"""Every platform adapter implements this interface. Add a new platform by subclassing it."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Awaitable, Callable, Optional

from fastapi import Request, Response

from ..models import UniversalMessage, UniversalReply

# Given to a push-style adapter's start_listening(): route a parsed message
# through the agent and return whatever reply (if any) should be sent back.
MessageHandler = Callable[[UniversalMessage], Awaitable[Optional[UniversalReply]]]


class PlatformAdapter(ABC):
    name: str

    @abstractmethod
    async def parse_webhook(self, request: Request) -> list[UniversalMessage]:
        """Turn an inbound webhook request into zero or more UniversalMessages.
        Not used by push-style adapters (see start_listening)."""

    @abstractmethod
    async def send_message(self, reply: UniversalReply) -> None:
        """Deliver a reply back to the platform."""

    async def verify_webhook(self, request: Request, body: bytes) -> bool:
        """Return False to reject a request (e.g. bad signature). Default: accept everything."""
        return True

    async def handle_handshake(self, request: Request, body: bytes) -> Optional[Response]:
        """Some platforms require a special response to a verification/challenge request
        instead of normal message processing. Return a Response to short-circuit, or None
        to continue with normal parse_webhook handling.
        """
        return None

    is_push_adapter: bool = False
    """Set True on subclasses that receive messages over a persistent connection
    (e.g. Discord's Gateway) instead of webhooks — the server will call
    start_listening() at startup instead of routing /webhook/{platform} to them."""

    async def start_listening(self, handle: MessageHandler) -> None:
        """For push-style adapters: connect, and for each inbound message call
        `handle(message)`, sending the returned reply (if any) via send_message.
        Runs for the lifetime of the app; raising here logs and does not crash
        the connector.
        """
        raise NotImplementedError

    async def stop_listening(self) -> None:
        """Counterpart to start_listening: release the connection on shutdown."""
        return None
