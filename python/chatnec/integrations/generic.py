"""The universal adapter: wrap almost anything into an AgentHandler.

Every framework's "agent" boils down to some callable that takes text (and maybe
conversation history) and returns text. `from_function` wraps that callable so it
satisfies chatnec's AgentHandler signature, handling both sync and async functions.
"""
from __future__ import annotations

import asyncio
import inspect
from typing import Any, Awaitable, Callable, Union

from ..models import AgentHandler, UniversalMessage
from ..session import InMemorySessionStore, SessionStore, conversation_key

SimpleFn = Callable[[str], Union[str, Awaitable[str]]]
ContextFn = Callable[[str, dict[str, Any]], Union[str, Awaitable[str]]]


def from_function(
    fn: Union[SimpleFn, ContextFn],
    session_store: SessionStore | None = None,
) -> AgentHandler:
    """Wrap `fn(text) -> str` or `fn(text, context) -> str` (sync or async) as an AgentHandler.

    `context` (if your function accepts a second argument) is a dict with the
    conversation's stored state plus platform/user metadata — mutate it and it's
    persisted for the next turn in the same conversation.
    """
    store = session_store or InMemorySessionStore()
    takes_context = len(inspect.signature(fn).parameters) >= 2

    async def handler(message: UniversalMessage) -> str:
        key = conversation_key(message.platform, message.chat_id, message.thread_id)
        state = await store.get(key) or {}

        if takes_context:
            context = {
                **state,
                "platform": message.platform,
                "user_id": message.user_id,
                "user_name": message.user_name,
            }
            result = fn(message.text, context)  # type: ignore[call-arg]
        else:
            result = fn(message.text)  # type: ignore[call-arg]
            context = state

        if inspect.isawaitable(result):
            result = await result

        await store.set(key, context)
        return result  # type: ignore[return-value]

    return handler
