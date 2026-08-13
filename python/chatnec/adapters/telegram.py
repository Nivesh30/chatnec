"""Telegram Bot API adapter (webhook mode)."""
from __future__ import annotations

from typing import Optional

import httpx
from fastapi import Request

from ..models import UniversalMessage, UniversalReply
from .base import PlatformAdapter


class TelegramAdapter(PlatformAdapter):
    name = "telegram"

    def __init__(self, bot_token: str, webhook_secret_token: Optional[str] = None) -> None:
        self.bot_token = bot_token
        self.webhook_secret_token = webhook_secret_token
        self._client = httpx.AsyncClient(
            base_url=f"https://api.telegram.org/bot{bot_token}",
            timeout=15.0,
        )

    async def verify_webhook(self, request: Request, body: bytes) -> bool:
        if not self.webhook_secret_token:
            return True
        header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        return header == self.webhook_secret_token

    async def parse_webhook(self, request: Request) -> list[UniversalMessage]:
        payload = await request.json()
        message = payload.get("message") or payload.get("edited_message")
        if not message or "text" not in message:
            return []

        chat = message["chat"]
        sender = message.get("from", {})

        return [
            UniversalMessage(
                platform=self.name,
                chat_id=str(chat["id"]),
                thread_id=str(message["message_thread_id"]) if message.get("message_thread_id") else None,
                user_id=str(sender.get("id", "unknown")),
                user_name=sender.get("username") or sender.get("first_name"),
                text=message["text"],
                raw=payload,
            )
        ]

    async def send_message(self, reply: UniversalReply) -> None:
        body: dict = {"chat_id": reply.chat_id, "text": reply.text}
        if reply.thread_id:
            body["message_thread_id"] = int(reply.thread_id)
        resp = await self._client.post("/sendMessage", json=body)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram send_message failed: {data.get('description')}")

    async def register_webhook(self, public_url: str) -> None:
        """Convenience helper: point Telegram's servers at this connector's /webhook/telegram."""
        body: dict = {"url": public_url}
        if self.webhook_secret_token:
            body["secret_token"] = self.webhook_secret_token
        resp = await self._client.post("/setWebhook", json=body)
        resp.raise_for_status()
