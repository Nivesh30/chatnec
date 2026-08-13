"""Pluggable conversation-state store, keyed by (platform, chat_id, thread_id).

Default is in-memory (fine for a single process / dev). Swap in Redis, a DB, etc.
by implementing the same three methods.
"""
from __future__ import annotations

from typing import Any, Optional, Protocol


def conversation_key(platform: str, chat_id: str, thread_id: Optional[str] = None) -> str:
    return f"{platform}:{chat_id}:{thread_id or ''}"


class SessionStore(Protocol):
    async def get(self, key: str) -> Optional[dict[str, Any]]: ...
    async def set(self, key: str, value: dict[str, Any]) -> None: ...
    async def delete(self, key: str) -> None: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def get(self, key: str) -> Optional[dict[str, Any]]:
        return self._data.get(key)

    async def set(self, key: str, value: dict[str, Any]) -> None:
        self._data[key] = value

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)
