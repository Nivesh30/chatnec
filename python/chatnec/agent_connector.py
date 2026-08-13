"""Forwards normalized messages to the agent, in one of two modes:

- Embedded: the agent handler is an in-process async callable (fastest, simplest,
  works for any framework you can wrap in one function).
- HTTP: the connector POSTs the message to AGENT_WEBHOOK_URL and treats the JSON
  response as the reply. Lets the agent live in a different process/language/host.
"""
from __future__ import annotations

from typing import Optional, Union

import httpx

from .models import AgentHandler, UniversalMessage, UniversalReply


class EmbeddedAgentConnector:
    def __init__(self, handler: AgentHandler) -> None:
        self.handler = handler

    async def handle(self, message: UniversalMessage) -> Optional[UniversalReply]:
        result = await self.handler(message)
        return _coerce_reply(result, message)


class HTTPAgentConnector:
    def __init__(self, webhook_url: str, timeout_seconds: float = 30.0) -> None:
        self.webhook_url = webhook_url
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def handle(self, message: UniversalMessage) -> Optional[UniversalReply]:
        resp = await self._client.post(self.webhook_url, json=message.model_dump())
        resp.raise_for_status()
        if not resp.content:
            return None
        data = resp.json()
        if data is None or "text" not in data:
            return None
        return UniversalReply.to(
            message,
            text=data["text"],
            attachments=data.get("attachments", []),
            metadata=data.get("metadata", message.metadata),
        )


def _coerce_reply(
    result: Union[str, UniversalReply, None], message: UniversalMessage
) -> Optional[UniversalReply]:
    if result is None:
        return None
    if isinstance(result, UniversalReply):
        return result
    return UniversalReply.to(message, text=result)
