"""Wire GitHub Copilot CLI up to Slack/Telegram/Teams/WhatsApp/Discord.

There are two different "GitHub Copilot CLI" surfaces — pick the one that
matches what you have installed:

1. The `gh copilot` extension (`gh extension install github/gh-copilot`) —
   `gh copilot suggest`/`gh copilot explain`. Narrow: it suggests or explains
   a single shell command, it isn't a general open-ended coding agent. Only
   worth wiring up if that's literally the use case you want in chat.
2. The standalone GitHub Copilot CLI agent (`npm install -g @github/copilot`,
   invoked as `copilot`) — a general coding agent comparable to Claude Code /
   Codex CLI, which is what this example targets.

NOTE ON FLAGS: this tool is newer and moves faster than Claude Code's CLI, so
treat the exact flags below as a starting point, not gospel — run
`copilot --help` and adjust `build_command`/`parse_output` to match your
installed version. The shape (non-interactive prompt in, text out, some form
of session/resume flag for continuity) is the part that's stable; the exact
flag names are the part to verify.

SECURITY: like Claude Code, this agent can read/write files and run shell
commands inside REPO_DIR, triggered by a chat message from anyone who can
reach your bot. See chatnec.integrations.cli_agent's module docstring.
"""
from chatnec import create_app
from chatnec.integrations.cli_agent import from_cli_agent

REPO_DIR = "/path/to/your/repo"


def build_command(text: str, context: dict) -> list[str]:
    cmd = ["copilot", "-p", text, "--allow-all-tools"]
    if session_id := context.get("session_id"):
        cmd += ["--resume", session_id]
    return cmd


def parse_output(output: str, context: dict) -> str:
    # If your installed version supports structured output (check
    # `copilot --help` for something like --output-format json) switch this
    # to json.loads(output) and stash the session id in context, the same
    # way examples/claude_code_agent.py does — that's what makes --resume
    # above actually continue the same session on the next message.
    return output.strip() or "(no output)"


agent = from_cli_agent(build_command, cwd=REPO_DIR, output_parser=parse_output)
app = create_app(handler=agent)
