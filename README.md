# chatnec

A universal chat connector: one normalized message format, adapters for Slack,
Telegram, and Microsoft Teams, and a single-function integration point so any
agent — regardless of framework or language — can be wired up in a few lines.

```
Slack ─┐                                   ┌─ your agent (in-process handler)
Telegram ─┼─▶ chatnec connector (FastAPI) ──┤
Teams ─┘        normalizes to               └─ or: POST to any HTTP endpoint
                 UniversalMessage/Reply         (any language, any framework)
```

## Why

Every chat platform has its own webhook shape, auth scheme, and reply API.
chatnec absorbs all of that behind one interface:

- **`UniversalMessage`** — what every adapter normalizes inbound events into.
- **`UniversalReply`** — what you send back; the right adapter delivers it.
- **`AgentHandler`** — the one function signature your agent needs to implement:
  `async (UniversalMessage) -> str | UniversalReply | None`.

Two ways to plug an agent in:

1. **Embedded** — pass your handler straight into `create_app()`. Runs in the
   same process as the connector. Simplest option for Python agents.
2. **HTTP** — point the connector at `AGENT_WEBHOOK_URL`. Your agent can then
   live anywhere, in any language — it just needs to accept a `UniversalMessage`
   JSON body and return `{"text": "..."}`. This is what the TypeScript SDK
   (`ts-sdk/`) wraps for Node-based frameworks.

## Demo

See [`docs/demo.md`](docs/demo.md) for a captured terminal transcript of the
full webhook → agent → reply round trip running locally (including
per-conversation context persisting across turns), plus the test suite passing.

## Quickstart (Python, embedded)

```bash
cd python
pip install -e .
cp env.example .env   # fill in TELEGRAM_BOT_TOKEN and/or SLACK_*/TEAMS_*
```

```python
# any callable becomes a bot on every configured platform
from chatnec import create_app
from chatnec.integrations import from_function

def my_agent(text: str) -> str:
    return f"You said: {text}"

app = create_app(handler=from_function(my_agent))
```

```bash
uvicorn examples.embedded_mode:app --reload
```

Point the platform's webhook at `https://<your-host>/webhook/<platform>`
(`slack`, `telegram`, or `teams`) — see comments in `python/env.example` for
per-platform setup notes.

Wiring an existing framework (LangChain shown, same pattern for CrewAI, AutoGen,
OpenAI Assistants, etc.) — see `python/chatnec/integrations/langchain.py` and
`python/examples/langchain_agent.py`.

## Quickstart (any language, HTTP mode)

Run the connector standalone:

```bash
AGENT_MODE=http AGENT_WEBHOOK_URL=http://localhost:9000/agent \
  uvicorn examples.standalone_service:app --reload
```

And your agent, in whatever language/framework you like, just needs to answer
POSTs with `{"text": "..."}`. For Node.js, the TS SDK does this for you:

```ts
import { createAgentServer } from "@chatnec/sdk";

createAgentServer(async (message) => {
  return `You said: ${message.text}`; // swap in LangChain.js, Vercel AI SDK, etc.
}, { port: 9000 });
```

## Layout

```
python/chatnec/
  models.py          UniversalMessage, UniversalReply, AgentHandler
  adapters/           slack.py, telegram.py, teams.py, base.py (add new platforms here)
  agent_connector.py  embedded vs HTTP dispatch to your agent
  server.py           FastAPI app: /webhook/{platform}, /reply, /health
  integrations/       from_function (generic), from_langchain_runnable (example)
  session.py          per-conversation state store (in-memory by default, pluggable)
ts-sdk/src/           createAgentServer + ChatConnectorClient for Node agents
```

## Adding a new platform

Subclass `chatnec.adapters.base.PlatformAdapter` and implement `parse_webhook`
and `send_message`; register it in `_build_adapters_from_settings()` in
`server.py` (or just pass `adapters={...}` to `create_app()` directly). See
[`docs/architecture.md`](docs/architecture.md) for the full message flow and
design rationale.

## Tests

```bash
cd python && pytest
```
