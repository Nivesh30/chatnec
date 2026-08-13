"""Pluggable conversation-state store, keyed by (platform, chat_id, thread_id).

Default is in-memory (fine for a single process / dev). Swap in Redis, a DB, etc.
by implementing the same three methods.
"""
from __future__ import annotations

import json
from typing import Any, Optional, Protocol


def conversation_key(platform: str, chat_id: str, thread_id: Optional[str] = None) -> str:
    return f"{platform}:{chat_id}:{thread_id or ''}"


class SessionStore(Protocol):
    async def get(self, key: str) -> Optional[dict[str, Any]]: ...
    async def set(self, key: str, value: dict[str, Any]) -> None: ...
    async def delete(self, key: str) -> None: ...


class InMemorySessionStore:
    """Fine for a single process / dev. State is lost on restart and isn't
    shared across processes — use RedisSessionStore once you scale beyond one.
    """

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def get(self, key: str) -> Optional[dict[str, Any]]:
        return self._data.get(key)

    async def set(self, key: str, value: dict[str, Any]) -> None:
        self._data[key] = value

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)


class RedisSessionStore:
    """Durable, multi-process-safe conversation state. Requires `redis`:
    pip install chatnec[redis]

    Keys expire after `ttl_seconds` of inactivity (default 30 days) so
    abandoned conversations don't accumulate forever.
    """

    def __init__(self, redis_url: str, key_prefix: str = "chatnec:session:", ttl_seconds: int = 60 * 60 * 24 * 30) -> None:
        try:
            from redis.asyncio import from_url
        except ImportError as exc:
            raise RuntimeError("RedisSessionStore requires redis: pip install chatnec[redis]") from exc

        self._redis = from_url(redis_url, decode_responses=True)
        self._key_prefix = key_prefix
        self._ttl_seconds = ttl_seconds

    def _full_key(self, key: str) -> str:
        return f"{self._key_prefix}{key}"

    async def get(self, key: str) -> Optional[dict[str, Any]]:
        raw = await self._redis.get(self._full_key(key))
        return json.loads(raw) if raw is not None else None

    async def set(self, key: str, value: dict[str, Any]) -> None:
        await self._redis.set(self._full_key(key), json.dumps(value), ex=self._ttl_seconds)

    async def delete(self, key: str) -> None:
        await self._redis.delete(self._full_key(key))


def default_session_store() -> SessionStore:
    """RedisSessionStore if REDIS_URL is set in the environment, else in-memory."""
    from .config import settings

    if settings.redis_url:
        return RedisSessionStore(settings.redis_url)
    return InMemorySessionStore()
