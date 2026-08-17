"""Wrap a non-interactive CLI coding agent (Claude Code, GitHub Copilot CLI,
Codex CLI, etc.) as an AgentHandler by shelling out to it per message.

These tools aren't importable Python objects like LangChain or CrewAI — you
invoke them as a subprocess with a prompt argument and read the result back
from stdout. This wrapper handles that shape generically: you supply a
`command(text, context) -> argv` function to build the command line for one
turn, and an optional `output_parser(output, context) -> str` to turn raw
stdout into the reply text — and, critically, to stash a session/resume ID in
`context` so the next message in the same conversation continues the same
CLI session instead of starting fresh each time.

SECURITY: these agents can read/write files and run shell commands on
whatever machine runs the connector. Wiring one up means a chat message can
trigger code execution — a materially bigger blast radius than a normal LLM
reply. Scope the working directory to something you're comfortable an
external chat message could affect, restrict who can reach the webhook, and
prefer running the connector in a low-privilege container/VM over your main
machine.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional, Sequence

from ..models import AgentHandler, UniversalMessage
from ..session import SessionStore, conversation_key, default_session_store

logger = logging.getLogger("chatnec")

CommandBuilder = Callable[[str, dict], Sequence[str]]
OutputParser = Callable[[str, dict], str]


def from_cli_agent(
    command: CommandBuilder,
    cwd: Optional[str] = None,
    timeout_seconds: float = 300.0,
    session_store: Optional[SessionStore] = None,
    output_parser: Optional[OutputParser] = None,
) -> AgentHandler:
    """Wrap a CLI coding agent as an AgentHandler.

    `command(text, context)` builds the argv for one turn — `context` is the
    same per-conversation dict chatnec.integrations.from_function uses, so
    you can read a previously-stored session ID out of it to resume.

    `output_parser(output, context)` turns raw stdout into reply text; it can
    mutate `context` (e.g. to record a session ID parsed out of structured
    output) and that mutation is persisted for the next turn. Defaults to
    `output.strip()` with no context mutation.
    """
    store = session_store or default_session_store()

    async def handler(message: UniversalMessage) -> str:
        key = conversation_key(message.platform, message.chat_id, message.thread_id)
        context = await store.get(key) or {}
        context.setdefault("platform", message.platform)
        context.setdefault("user_id", message.user_id)
        context.setdefault("user_name", message.user_name)

        argv = list(command(message.text, context))

        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            await store.set(key, context)
            return "Sorry, that took too long and was cancelled."

        if proc.returncode != 0:
            logger.error(
                "chatnec: CLI agent %s exited %s: %s",
                argv[0],
                proc.returncode,
                stderr.decode(errors="replace")[:2000],
            )
            await store.set(key, context)
            return "Sorry, something went wrong running that."

        output = stdout.decode(errors="replace")
        # output_parser may mutate context (e.g. stash a session ID to resume next
        # turn) — persist it *after* that runs, not before.
        result = output_parser(output, context) if output_parser else output.strip()
        await store.set(key, context)
        return result

    return handler
