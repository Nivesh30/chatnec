"""Wire GitHub Copilot CLI up to Slack/Telegram/Teams/WhatsApp/Discord.

Targets the standalone GitHub Copilot CLI agent (`npm install -g
@github/copilot`, invoked as `copilot`) — a general coding agent comparable
to Claude Code / Codex CLI. `gh copilot` (the `gh` extension) now delegates
straight to this same binary on recent `gh` versions rather than being a
separate, narrower "suggest a shell command" tool, so either entrypoint works
— check `gh copilot --help` / `gh --version` if you're on an older `gh`.

Flags below verified against `copilot --help` (v0.0.420): -p/--prompt for a
non-interactive run, --allow-all-tools (required for non-interactive mode —
without it, a tool call blocks waiting for a permission prompt that never
comes), and --resume=<sessionId>.

Unlike Claude Code (which assigns a session ID and hands it back to you in
its JSON output), Copilot CLI's --resume doubles as "create": passing a UUID
that doesn't exist yet starts a new session pinned to that exact ID (see
`copilot --help`'s "Start a new session with a specific UUID" example). So
instead of running a message, parsing structured output for a session ID,
and threading it through, we just generate one UUID the first time we see a
conversation and pass --resume=<that-uuid> on every turn from then on — no
output parsing needed for continuity at all.

(--output-format json is available too, but it's JSONL — one JSON object per
line, i.e. an event stream — not a single result object like Claude Code's.
Parsing that for anything beyond raw text needs scanning the event stream;
inspect a real run's output for your installed version before building a
parser against it.)

SECURITY: like Claude Code, this agent can read/write files and run shell
commands inside REPO_DIR, triggered by a chat message from anyone who can
reach your bot. See chatnec.integrations.cli_agent's module docstring.
"""
import uuid

from chatnec import create_app
from chatnec.integrations.cli_agent import from_cli_agent

REPO_DIR = "/path/to/your/repo"


def build_command(text: str, context: dict) -> list[str]:
    session_id = context.setdefault("session_id", str(uuid.uuid4()))
    return ["copilot", "-p", text, "--allow-all-tools", f"--resume={session_id}"]


def parse_output(output: str, context: dict) -> str:
    return output.strip() or "(no output)"


agent = from_cli_agent(build_command, cwd=REPO_DIR, output_parser=parse_output)
app = create_app(handler=agent)
