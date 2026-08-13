"""WhatsApp adapter via the Meta WhatsApp Business Cloud API.

Setup: create a Meta app with the WhatsApp product, point its webhook at
https://<your-host>/webhook/whatsapp, subscribe to the "messages" field, and
set verify_token to whatever you configure in the Meta dashboard's webhook
verification step (Meta calls this a GET handshake, not the POST events).
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Optional

import httpx
from fastapi import Request, Response

from ..models import UniversalMessage, UniversalReply
from ..retry import send_with_retry
from .base import PlatformAdapter

GRAPH_API_BASE = "https://graph.facebook.com/v20.0"


class WhatsAppAdapter(PlatformAdapter):
    name = "whatsapp"

    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
        app_secret: Optional[str] = None,
        verify_token: Optional[str] = None,
    ) -> None:
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.app_secret = app_secret
        self.verify_token = verify_token
        self._client = httpx.AsyncClient(
            base_url=GRAPH_API_BASE,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15.0,
        )

    async def verify_webhook(self, request: Request, body: bytes) -> bool:
        if not self.app_secret:
            return True

        signature = request.headers.get("X-Hub-Signature-256", "")
        if not signature.startswith("sha256="):
            return False

        expected = hmac.new(self.app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature)

    async def handle_handshake(self, request: Request, body: bytes) -> Optional[Response]:
        # Meta's webhook verification is a GET with query params, not POST — routed
        # here via server.py's GET /webhook/{platform} passthrough.
        if request.method != "GET":
            return None

        params = request.query_params
        if (
            params.get("hub.mode") == "subscribe"
            and self.verify_token
            and params.get("hub.verify_token") == self.verify_token
        ):
            return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
        return Response(status_code=403)

    async def parse_webhook(self, request: Request) -> list[UniversalMessage]:
        payload = await request.json()
        messages: list[UniversalMessage] = []

        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                contacts = {c["wa_id"]: c for c in value.get("contacts", [])}

                for msg in value.get("messages", []):
                    if msg.get("type") != "text":
                        continue
                    sender_id = msg["from"]
                    contact = contacts.get(sender_id, {})

                    messages.append(
                        UniversalMessage(
                            platform=self.name,
                            chat_id=sender_id,
                            user_id=sender_id,
                            user_name=contact.get("profile", {}).get("name"),
                            text=msg["text"]["body"],
                            raw=payload,
                        )
                    )

        return messages

    async def send_message(self, reply: UniversalReply) -> None:
        body = {
            "messaging_product": "whatsapp",
            "to": reply.chat_id,
            "type": "text",
            "text": {"body": reply.text},
        }
        resp = await send_with_retry(
            lambda: self._client.post(f"/{self.phone_number_id}/messages", json=body)
        )
        resp.raise_for_status()
