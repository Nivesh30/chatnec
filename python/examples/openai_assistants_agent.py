"""Wiring an OpenAI Assistant up to Slack/Telegram/Teams/WhatsApp.
Requires: pip install chatnec[openai]

Uses a persistent OpenAI thread per chatnec conversation — `context` (persisted
per platform/chat/thread) just needs to remember the OpenAI thread_id, and the
Assistants API handles the actual message history.
"""
import asyncio

from openai import AsyncOpenAI
from chatnec import create_app
from chatnec.integrations import from_function

client = AsyncOpenAI()
ASSISTANT_ID = "asst_..."  # your existing assistant


async def run_assistant(text: str, context: dict) -> str:
    thread_id = context.get("openai_thread_id")
    if thread_id is None:
        thread = await client.beta.threads.create()
        thread_id = context["openai_thread_id"] = thread.id

    await client.beta.threads.messages.create(thread_id=thread_id, role="user", content=text)
    run = await client.beta.threads.runs.create(thread_id=thread_id, assistant_id=ASSISTANT_ID)

    while run.status in ("queued", "in_progress"):
        await asyncio.sleep(1)
        run = await client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)

    messages = await client.beta.threads.messages.list(thread_id=thread_id, limit=1)
    return messages.data[0].content[0].text.value


app = create_app(handler=from_function(run_assistant))
