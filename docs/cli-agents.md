[← back to README](../README.md)

# CLI coding agents: Claude Code, GitHub Copilot CLI & Codex CLI

Setup for wiring [`from_cli_agent`](../python/chatnec/integrations/cli_agent.py)
up to Claude Code, GitHub Copilot CLI, and Codex CLI — the three examples
that ship in [`python/examples/`](../python/examples/). The commands and
flags on this page were checked against a real install of each tool while
writing it (versions noted below, with one exception noted in the Codex CLI
section); if your installed version differs, `<tool> --help` is the source
of truth, not this page.

> **"GitHub CLI" vs. "GitHub Copilot CLI"**: plain `gh` (the GitHub CLI) is
> not a coding agent — it has no non-interactive "give it a prompt, get a
> reply" mode, so there's nothing for `from_cli_agent` to wrap. What's
> covered below is **GitHub Copilot CLI** (`copilot`, or `gh copilot` on a
> recent `gh`), the actual agent. If you meant `gh` itself — e.g. having an
> agent run `gh pr create` as one of its tools — that's a capability you'd
> grant the agent (Claude Code, Copilot CLI, or Codex CLI can all shell out
> to `gh` on their own if it's installed and authenticated in the
> connector's environment), not a separate `from_cli_agent` integration.

> **Before anything else, read the security note.** Wiring either of these
> up means a chat message can trigger code execution on whatever machine
> runs the connector. See the "Security" callout in
> [`cli_agent.py`](../python/chatnec/integrations/cli_agent.py) and the
> [README's Security section](../README.md#security) — at minimum, add your
> own check on `message.user_id` before invoking the CLI agent so only
> people you trust can reach it.

## Claude Code

Verified against Claude Code v2.1.83.

**Install & auth** — `npm install -g @anthropic-ai/claude-code`, then run
`claude` once interactively to sign in (or set `ANTHROPIC_API_KEY`).

**Verify it works standalone** before wiring it into chatnec:

```bash
claude -p "What is 2+2? Answer with just the number." --output-format json
```

This should print one JSON object on a single line containing `"result"`
(the answer text) and `"session_id"` (a UUID) — confirmed by running exactly
this command. Passing `-r`/`--resume <that-session-id>` on a later call
continues the same conversation; `cache_read_input_tokens` showing up
non-zero on the resumed call is your evidence it actually loaded prior
context rather than starting fresh (also confirmed by testing).

**Wire it in** — [`examples/claude_code_agent.py`](../python/examples/claude_code_agent.py)
does exactly the above: builds `claude -p <text> --output-format json`, adds
`--resume <session_id>` once one exists, and parses the JSON `result`/
`session_id` fields. Edit `REPO_DIR` to point at the repo you want it
operating on, then:

```bash
cd python
uvicorn examples.claude_code_agent:app --reload
```

## GitHub Copilot CLI

Verified against `@github/copilot` v0.0.420.

Two entrypoints exist and — on a recent `gh` — resolve to the same thing:

- The standalone binary: `npm install -g @github/copilot`, invoked as `copilot`
- `gh copilot` (the `gh` extension): on this environment's `gh` version, `gh
  copilot --help` shows it now downloads and delegates straight to the same
  standalone `copilot` binary, rather than being the older, narrower "suggest
  a shell command" tool. If you're on an older `gh`, `gh copilot suggest`/
  `gh copilot explain` may still be the separate, narrower command-suggestion
  tool — check your version.

**Install & auth** — `npm install -g @github/copilot`, then run `copilot`
once interactively to sign in.

**Verify it works standalone**:

```bash
copilot -p "What is 2+2? Answer with just the number." --allow-all-tools
```

`--allow-all-tools` is required for non-interactive use — without it, the
first tool call blocks waiting for an interactive permission prompt that
never arrives (confirmed: omitting it hangs a non-interactive run).

> **Org policy note**: while verifying this, running `copilot` in this
> environment failed with `Error: Access denied by policy settings — Your
> organization has restricted Copilot access`. That's a real error you may
> hit too — it means your GitHub org's Copilot CLI policy needs enabling by
> an admin (https://github.com/settings/copilot), not a chatnec or install
> problem. If you hit this, that's where to look.

**Session continuity works differently than Claude Code**: `--resume` here
doubles as "create" — passing a UUID that doesn't exist yet starts a new
session pinned to that exact ID (see `copilot --help`'s example: `copilot
--resume=0cb916db-26aa-40f2-86b5-1ba81b225fd2`). So rather than parsing
output for a session ID, [`examples/github_copilot_cli_agent.py`](../python/examples/github_copilot_cli_agent.py)
just generates one UUID per conversation and always passes
`--resume=<that-uuid>` — no output parsing needed for continuity. Note the
`=` — `--resume` takes an optional value, so `--resume <id>` as two separate
argv entries is ambiguous and may not parse the way you'd expect; `--resume=<id>`
is unambiguous.

`--output-format json` exists but wasn't something the org-policy block let
us verify the exact shape of here — it's documented as JSONL (one JSON
object per line, i.e. an event stream), not a single result object the way
Claude Code's is. The shipped example sticks to plain-text output for that
reason; if you want structured parsing, run a sample query with
`--output-format json` yourself first and inspect what your installed
version actually emits before writing a parser against it.

**Wire it in**:

```bash
cd python
uvicorn examples.github_copilot_cli_agent:app --reload
```

## Codex CLI

Verified against `codex-cli` v0.149.1's `--help` output (`codex exec --help`,
`codex exec resume --help`). This environment has no OpenAI credentials to
run a live `codex exec` and capture real output — unlike the two sections
above, the `--json` event shapes below are sourced from
[OpenAI's own non-interactive-mode docs](https://developers.openai.com/codex/noninteractive),
not a captured transcript, so double-check them against your own
`codex exec --json '...'` output before relying on this in production.

**Install & auth** — `npm install -g @openai/codex`, then run `codex login`
(or run `codex` once interactively) to sign in.

**Verify it works standalone** before wiring it into chatnec:

```bash
codex exec --json "What is 2+2? Answer with just the number."
```

With `--json`, stdout is JSONL (one JSON object per line) rather than a
single result object like Claude Code's. Two event types matter here:

```json
{"type":"thread.started","thread_id":"<uuid>"}
{"type":"item.completed","item":{"id":"item_3","type":"agent_message","text":"4"}}
```

`thread_id` from `thread.started` is what you pass back in to continue the
same session; the final reply text is the `text` field of the
`item.completed` event whose `item.type` is `"agent_message"` (other item
types cover command execution, file changes, MCP calls, etc. — skip those).

Resuming a session takes the thread ID as a positional argument, not a flag:

```bash
codex exec resume <thread_id> --json "follow-up question"
```

**Wire it in** — [`examples/codex_cli_agent.py`](../python/examples/codex_cli_agent.py)
does exactly the above: builds `codex exec --json <text>` for a new
conversation, switches to `codex exec resume <thread_id> --json <text>` once
a `thread_id` has been captured, and scans the JSONL output for
`thread.started` / `item.completed` events. Edit `REPO_DIR` to point at the
repo you want it operating on, then:

```bash
cd python
uvicorn examples.codex_cli_agent:app --reload
```

**Sandboxing**: unlike Copilot CLI (which needs an explicit
`--allow-all-tools` flag to avoid blocking on a permission prompt), Codex's
`exec` mode doesn't stop for interactive approval at all — it runs
model-generated shell commands directly within whatever `--sandbox` policy
is in effect (`workspace-write` by default; `read-only` or
`danger-full-access` are the other options, and
`--dangerously-bypass-approvals-and-sandbox` removes the sandbox entirely).
That default is more permissive than Claude Code's, which does prompt for
tool approval outside `-p`/print mode — worth knowing given the Security
note at the top of this page.

## Testing your wiring without a real chat platform

All three examples build a normal chatnec `app`, so the same pattern from
[`docs/demo.md`](demo.md) applies — swap in a `DemoPlatformAdapter` instead
of pointing a real webhook at it, and drive it with `curl`:

```python
# examples/claude_code_demo.py — same idea as demo_fake_platform.py, wired to Claude Code instead
from chatnec import create_app
from chatnec.adapters.base import PlatformAdapter
from chatnec.integrations.cli_agent import from_cli_agent
from chatnec.models import UniversalMessage, UniversalReply

class DemoPlatformAdapter(PlatformAdapter):
    name = "demo"
    async def parse_webhook(self, request):
        payload = await request.json()
        return [UniversalMessage(platform=self.name, chat_id=payload["chat_id"], user_id="demo-user", text=payload["text"])]
    async def send_message(self, reply: UniversalReply) -> None:
        print(f"[claude code -> chat {reply.chat_id}]: {reply.text}")

# ... build_command / parse_output from examples/claude_code_agent.py ...
agent = from_cli_agent(build_command, cwd="/path/to/repo", output_parser=parse_output)
app = create_app(handler=agent, adapters={"demo": DemoPlatformAdapter()})
```

```bash
uvicorn examples.claude_code_demo:app --port 8123 &
curl -X POST http://127.0.0.1:8123/webhook/demo \
  -H "Content-Type: application/json" \
  -d '{"chat_id":"c1","text":"What does this repo do?"}'
```

## Other CLI agents

Same recipe as the three above: check `<tool> --help` for its non-interactive
prompt flag and its session/resume mechanism, write a `build_command`/
`parse_output` pair, and pass them to `from_cli_agent`. The things worth
checking for any new one:

- What's the non-interactive/print-mode flag (usually `-p`)?
- Does it need an explicit "allow tools without prompting" flag to actually
  run unattended (Copilot does; check whether yours does too)?
- Is structured/JSON output a single object (parse directly) or a stream
  (JSONL — parse line by line, or avoid it and stick to plain text)?
- Does resume take a session ID that *you* choose (Copilot CLI: generate a
  UUID yourself, no output parsing needed) or one the *tool* assigns
  (Claude Code: capture it from a first response, thread it through)?
