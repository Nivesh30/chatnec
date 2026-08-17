"""Wire Claude Code up to Slack/Telegram/Teams/WhatsApp/Discord — chat with it
from wherever your team already talks, instead of only a terminal.

"Claude CLI" and "Claude Code" refer to the same tool here (`claude`); this
example covers both.

Claude Code runs non-interactively via `claude -p "<prompt>"` (print mode).
`--output-format json` gets you a structured response including `session_id`,
which we stash in chatnec's per-conversation context and pass back in via
`--resume` — so each chat thread maps to one continuous Claude Code session
instead of starting fresh every message.

SECURITY: Claude Code can read/write files and run shell commands inside
REPO_DIR. Anyone who can message your bot can trigger it. Point REPO_DIR at
something you're comfortable an external chat message could affect, and
run the connector in a sandboxed/low-privilege environment — see
chatnec.integrations.cli_agent's module docstring.
"""
import json

from chatnec import create_app
from chatnec.integrations.cli_agent import from_cli_agent

REPO_DIR = "/path/to/your/repo"


def build_command(text: str, context: dict) -> list[str]:
    cmd = ["claude", "-p", text, "--output-format", "json"]
    if session_id := context.get("session_id"):
        cmd += ["--resume", session_id]
    return cmd


def parse_output(output: str, context: dict) -> str:
    data = json.loads(output)
    if session_id := data.get("session_id"):
        context["session_id"] = session_id
    return data.get("result", "").strip() or "(no output)"


agent = from_cli_agent(build_command, cwd=REPO_DIR, output_parser=parse_output)
app = create_app(handler=agent)
