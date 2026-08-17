"""Acts as *you* in Microsoft Teams via delegated Microsoft Graph permissions
(Chat.ReadWrite) — reads and sends chat messages as your own signed-in
identity, not as a separate bot that has to be added to a conversation. This
is a different integration model from TeamsAdapter (adapters/teams.py), which
is a Bot Framework bot; both can run at once under different platform names
("teams_user" vs "teams").

Requires an Azure AD app registration (public client) and running
`chatnec teams-login` once first — see chatnec.msgraph_auth and the README.

Push-style like DiscordAdapter (see PlatformAdapter.is_push_adapter), except
driven by polling rather than a persistent connection: Microsoft Graph has no
inbound webhook model that fits chatnec's per-message flow as simply as a
delta query does.
"""
from __future__ import annotations

import asyncio
import html
import logging
import re
from typing import Any, Optional

import httpx

from ..models import UniversalMessage, UniversalReply
from ..msgraph_auth import acquire_token_silent
from ..retry import send_with_retry
from .base import MessageHandler, PlatformAdapter

logger = logging.getLogger("chatnec")

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = ["Chat.ReadWrite", "User.Read"]

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(body: str) -> str:
    return html.unescape(_TAG_RE.sub("", body)).strip()


class TeamsUserAdapter(PlatformAdapter):
    name = "teams_user"
    is_push_adapter = True

    def __init__(
        self,
        client_id: str,
        tenant_id: str = "common",
        poll_interval_seconds: float = 15.0,
        token_cache_path: Optional[str] = None,
    ) -> None:
        self.client_id = client_id
        self.tenant_id = tenant_id
        self.poll_interval_seconds = poll_interval_seconds
        self.token_cache_path = token_cache_path
        self._client = httpx.AsyncClient(base_url=GRAPH_API_BASE, timeout=15.0)
        self._delta_links: dict[str, str] = {}
        self._me_id: Optional[str] = None
        self._stopped = False

    async def parse_webhook(self, request):  # pragma: no cover - not used, see module docstring
        return []

    async def _headers(self) -> dict[str, str]:
        token = await asyncio.to_thread(
            acquire_token_silent, self.client_id, self.tenant_id, SCOPES, self.token_cache_path
        )
        if not token:
            raise RuntimeError(
                "No cached Teams user credentials — run `chatnec teams-login` first"
            )
        return {"Authorization": f"Bearer {token}"}

    async def start_listening(self, handle: MessageHandler) -> None:
        headers = await self._headers()
        me = await self._client.get("/me", headers=headers)
        me.raise_for_status()
        me_data = me.json()
        self._me_id = me_data["id"]
        logger.info(
            "chatnec: Teams user adapter polling as %s every %.0fs",
            me_data.get("userPrincipalName", self._me_id),
            self.poll_interval_seconds,
        )

        while not self._stopped:
            try:
                await self._poll_once(handle)
            except Exception:
                logger.exception("chatnec: Teams user adapter poll failed")
            await asyncio.sleep(self.poll_interval_seconds)

    async def stop_listening(self) -> None:
        self._stopped = True

    async def _poll_once(self, handle: MessageHandler) -> None:
        headers = await self._headers()
        resp = await self._client.get("/me/chats", headers=headers, params={"$top": 50})
        resp.raise_for_status()
        for chat in resp.json().get("value", []):
            await self._poll_chat(chat["id"], headers, handle)

    async def _poll_chat(self, chat_id: str, headers: dict[str, str], handle: MessageHandler) -> None:
        # First time we see a chat, the delta query returns its entire history —
        # capture the deltaLink as a baseline instead of replaying old messages
        # through the agent.
        priming = chat_id not in self._delta_links
        url: Optional[str] = self._delta_links.get(chat_id, f"/chats/{chat_id}/messages/delta")

        while url:
            resp = await self._client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            if not priming:
                for item in data.get("value", []):
                    await self._handle_item(chat_id, item, handle)

            if delta_link := data.get("@odata.deltaLink"):
                self._delta_links[chat_id] = delta_link
            url = data.get("@odata.nextLink")

    async def _handle_item(self, chat_id: str, item: dict[str, Any], handle: MessageHandler) -> None:
        if item.get("messageType") != "message" or item.get("deletedDateTime"):
            return

        sender = ((item.get("from") or {}).get("user")) or {}
        if sender.get("id") == self._me_id:
            return  # ignore messages we sent ourselves

        text = _strip_html((item.get("body") or {}).get("content", ""))
        if not text:
            return

        umsg = UniversalMessage(
            platform=self.name,
            chat_id=chat_id,
            user_id=sender.get("id", "unknown"),
            user_name=sender.get("displayName"),
            text=text,
            raw=item,
        )

        try:
            reply = await handle(umsg)
        except Exception:
            logger.exception("chatnec: agent handler failed for Teams user message %s", umsg.id)
            return

        if reply is not None:
            await self.send_message(reply)

    async def send_message(self, reply: UniversalReply) -> None:
        headers = await self._headers()
        body = {"body": {"content": reply.text}}
        resp = await send_with_retry(
            lambda: self._client.post(f"/chats/{reply.chat_id}/messages", json=body, headers=headers)
        )
        resp.raise_for_status()
