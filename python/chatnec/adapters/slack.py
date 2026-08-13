"""Slack Events API adapter (bot token + signing secret, no Socket Mode required)."""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Optional

import httpx
from fastapi import Request, Response

from ..models import Attachment, UniversalMessage, UniversalReply
from .base import PlatformAdapter

SLACK_API_BASE = "https://slack.com/api"


class SlackAdapter(PlatformAdapter):
    name = "slack"

    def __init__(self, bot_token: str, signing_secret: Optional[str] = None) -> None:
        self.bot_token = bot_token
        self.signing_secret = signing_secret
        self._client = httpx.AsyncClient(
            base_url=SLACK_API_BASE,
            headers={"Authorization": f"Bearer {bot_token}"},
            timeout=15.0,
        )

    async def verify_webhook(self, request: Request, body: bytes) -> bool:
        if not self.signing_secret:
            return True  # verification disabled if no secret configured

        timestamp = request.headers.get("X-Slack-Request-Timestamp")
        signature = request.headers.get("X-Slack-Signature")
        if not timestamp or not signature:
            return False

        # Reject requests older than 5 minutes to mitigate replay attacks.
        if abs(time.time() - float(timestamp)) > 60 * 5:
            return False

        base = f"v0:{timestamp}:{body.decode('utf-8')}".encode("utf-8")
        digest = hmac.new(self.signing_secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
        expected = f"v0={digest}"
        return hmac.compare_digest(expected, signature)

    async def handle_handshake(self, request: Request, body: bytes) -> Optional[Response]:
        import json

        payload = json.loads(body or b"{}")
        if payload.get("type") == "url_verification":
            return Response(content=payload["challenge"], media_type="text/plain")
        return None

    async def parse_webhook(self, request: Request) -> list[UniversalMessage]:
        payload = await request.json()
        event = payload.get("event")
        if not event:
            return []

        # Ignore bot's own messages / edits / non-message subtypes to avoid loops.
        if event.get("bot_id") or event.get("subtype") is not None:
            return []
        if event.get("type") != "message":
            return []

        attachments = [
            Attachment(type="file", url=f.get("url_private"), name=f.get("name"), content_type=f.get("mimetype"))
            for f in event.get("files", [])
        ]

        return [
            UniversalMessage(
                platform=self.name,
                chat_id=event["channel"],
                thread_id=event.get("thread_ts") or event.get("ts"),
                user_id=event.get("user", "unknown"),
                text=event.get("text", ""),
                attachments=attachments,
                raw=payload,
            )
        ]

    async def send_message(self, reply: UniversalReply) -> None:
        body = {"channel": reply.chat_id, "text": reply.text}
        if reply.thread_id:
            body["thread_ts"] = reply.thread_id
        resp = await self._client.post("/chat.postMessage", json=body)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack send_message failed: {data.get('error')}")
