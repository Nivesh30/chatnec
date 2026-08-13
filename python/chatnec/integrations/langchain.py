"""Example wrapper for LangChain (Runnable / AgentExecutor). Optional — only imported
if you actually call this function, so LangChain isn't a hard dependency of chatnec.

The same five-line pattern works for CrewAI (`crew.kickoff(inputs=...)`), AutoGen
(`agent.generate_reply(...)`), OpenAI Assistants, or any other framework: pull the
per-conversation state chatnec already tracks, invoke the framework, return text.
"""
from __future__ import annotations

from typing import Any

from ..models import AgentHandler, UniversalMessage
from ..session import InMemorySessionStore, SessionStore, conversation_key


def from_langchain_runnable(
    runnable: Any,
    session_store: SessionStore | None = None,
    session_key_name: str = "session_id",
) -> AgentHandler:
    """Wrap a LangChain Runnable (e.g. an AgentExecutor or a RunnableWithMessageHistory)
    so its `.ainvoke` powers a chatnec agent. Each (platform, chat, thread) gets its
    own `session_id`, so LangChain's own memory/history classes stay scoped per-conversation.
    """
    store = session_store or InMemorySessionStore()

    async def handler(message: UniversalMessage) -> str:
        key = conversation_key(message.platform, message.chat_id, message.thread_id)

        result = await runnable.ainvoke(
            {"input": message.text},
            config={"configurable": {session_key_name: key}},
        )

        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            return result.get("output") or result.get("text") or str(result)
        return str(result)

    return handler
