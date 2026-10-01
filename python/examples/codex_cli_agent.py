"""Wire OpenAI Codex CLI up to Slack/Telegram/Teams/WhatsApp/Discord.

Codex CLI runs non-interactively via `codex exec <prompt> --json`. `--json`
switches stdout to JSONL (one JSON object per event) rather than a single
result object like Claude Code's `--output-format json`. The two events we
care about:

- `{"type": "thread.started", "thread_id": "<uuid>"}` — emitted once, first
- `{"type": "item.completed", "item": {"type": "agent_message", "text": "..."}}`
  — the agent's final reply text

We stash `thread_id` in chatnec's per-conversation context and pass it back
via `codex exec resume <thread_id> --json <prompt>` on later turns, the same
way the Claude Code example threads `session_id` through `--resume` — so a
chat thread maps to one continuous Codex session instead of starting fresh
every message.

Verified against `codex-cli` v0.149.1's `--help` output for every flag used
below (`codex exec --help`, `codex exec resume --help`). The `--json` event
shapes above are documented upstream; this environment has no OpenAI
credentials to run a live `codex exec` and capture real output, so — unlike
the Claude Code/Copilot CLI docs — confirm the exact field names against
`codex exec --json '...'` yourself before relying on this in production.

SECURITY: like Claude Code and Copilot CLI, this agent can read/write files
and run shell commands inside REPO_DIR, triggered by a chat message from
anyone who can reach your bot. Codex's own sandbox (`--sandbox`, default
`workspace-write`) limits what it can touch without prompting — but nothing
here replaces your own authorization check on `message.user_id` before
invoking it. See chatnec.integrations.cli_agent's module docstring.
"""
import json

from chatnec import create_app
from chatnec.integrations.cli_agent import from_cli_agent

REPO_DIR = "/path/to/your/repo"


def build_command(text: str, context: dict) -> list[str]:
    if thread_id := context.get("thread_id"):
        return ["codex", "exec", "resume", thread_id, "--json", text]
    return ["codex", "exec", "--json", text]


def parse_output(output: str, context: dict) -> str:
    reply = ""
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        event = json.loads(line)
        if event.get("type") == "thread.started" and event.get("thread_id"):
            context["thread_id"] = event["thread_id"]
        elif event.get("type") == "item.completed":
            item = event.get("item", {})
            if item.get("type") == "agent_message" and item.get("text"):
                reply = item["text"]
    return reply.strip() or "(no output)"


agent = from_cli_agent(build_command, cwd=REPO_DIR, output_parser=parse_output)
app = create_app(handler=agent)
