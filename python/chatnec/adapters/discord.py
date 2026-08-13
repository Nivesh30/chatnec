"""Discord adapter.

Unlike Slack/Telegram/Teams/WhatsApp, Discord has no push-webhook for regular
channel messages — receiving them requires a persistent Gateway (WebSocket)
connection. This adapter is therefore "push-style" (see PlatformAdapter.
is_push_adapter): instead of being routed to via /webhook/discord, the server
calls start_listening() once at startup and this adapter drives message
handling itself for as long as the app runs.

Requires the "Message Content" privileged intent to be enabled for your bot
in the Discord Developer Portal, or `message.content` will always be empty.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from ..models import UniversalMessage, UniversalReply
from ..retry import send_with_retry
from .base import MessageHandler, PlatformAdapter

logger = logging.getLogger("chatnec")

DISCORD_API_BASE = "https://discord.com/api/v10"


class DiscordAdapter(PlatformAdapter):
    name = "discord"
    is_push_adapter = True

    def __init__(self, bot_token: str) -> None:
        self.bot_token = bot_token
        self._client = httpx.AsyncClient(
            base_url=DISCORD_API_BASE,
            headers={"Authorization": f"Bot {bot_token}"},
            timeout=15.0,
        )
        self._discord_client: Optional[Any] = None

    async def parse_webhook(self, request):  # pragma: no cover - not used, see module docstring
        return []

    async def start_listening(self, handle: MessageHandler) -> None:
        try:
            import discord
        except ImportError as exc:
            raise RuntimeError(
                "The Discord adapter requires discord.py: pip install chatnec[discord]"
            ) from exc

        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)
        self._discord_client = client

        @client.event
        async def on_ready():
            logger.info("chatnec: Discord adapter connected as %s", client.user)

        @client.event
        async def on_message(message):
            if message.author.bot:
                return

            thread_id = str(message.channel.id) if isinstance(message.channel, discord.Thread) else None

            umsg = UniversalMessage(
                platform=self.name,
                chat_id=str(message.channel.id),
                thread_id=thread_id,
                user_id=str(message.author.id),
                user_name=str(message.author),
                text=message.content,
            )

            try:
                reply = await handle(umsg)
            except Exception:
                logger.exception("chatnec: agent handler failed for Discord message %s", umsg.id)
                return

            if reply is not None:
                await self.send_message(reply)

        await client.start(self.bot_token)

    async def stop_listening(self) -> None:
        if self._discord_client is not None:
            await self._discord_client.close()

    async def send_message(self, reply: UniversalReply) -> None:
        body = {"content": reply.text}
        resp = await send_with_retry(
            lambda: self._client.post(f"/channels/{reply.chat_id}/messages", json=body)
        )
        resp.raise_for_status()
