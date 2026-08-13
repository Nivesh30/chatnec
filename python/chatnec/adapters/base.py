"""Every platform adapter implements this interface. Add a new platform by subclassing it."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from fastapi import Request, Response

from ..models import UniversalMessage, UniversalReply


class PlatformAdapter(ABC):
    name: str

    @abstractmethod
    async def parse_webhook(self, request: Request) -> list[UniversalMessage]:
        """Turn an inbound webhook request into zero or more UniversalMessages."""

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
