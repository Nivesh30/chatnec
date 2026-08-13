<p align="center">
  <img alt="chatnec" src="assets/wordmark.svg" width="320">
</p>

<p align="center">
  One normalized message format. Adapters for Slack, Telegram, Teams, WhatsApp, and Discord.<br>
  A single function signature so any agent — any framework, any language — can be wired up in a few lines.
</p>

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="Node 18+" src="https://img.shields.io/badge/node-18%2B-339933?logo=node.js&logoColor=white">
  <img alt="Platforms" src="https://img.shields.io/badge/platforms-Slack%20%7C%20Telegram%20%7C%20Teams%20%7C%20WhatsApp%20%7C%20Discord-6366F1">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-6366F1">
</p>

---

## Contents

- [Why](#why)
- [How it works](#how-it-works)
- [Demo](#demo)
- [Quickstart — scaffold a project](#quickstart--scaffold-a-project)
- [Quickstart — Python, embedded](#quickstart--python-embedded)
- [Quickstart — any language, HTTP mode](#quickstart--any-language-http-mode)
- [Platform support](#platform-support)
- [Framework examples](#framework-examples)
- [Production](#production)
- [Layout](#layout)
- [Adding a new platform](#adding-a-new-platform)
- [Tests](#tests)

## Why

Every chat platform has its own webhook shape, auth scheme, and reply API —
Slack signs requests with HMAC, Telegram uses a bot-API secret token, Teams
signs with a Bot Framework JWT you validate against a JWKS endpoint, Discord
doesn't have inbound webhooks for messages at all (it's a persistent Gateway
connection). An agent that wants to run on all of them either reimplements
this five times or gets coupled to one platform's SDK.

chatnec absorbs all of that behind one interface:

- **`UniversalMessage`** — what every adapter normalizes inbound events into.
- **`UniversalReply`** — what you send back; the right adapter delivers it.
- **`AgentHandler`** — the one function signature your agent needs to implement:
  `async (UniversalMessage) -> str | UniversalReply | None`.

## How it works

```mermaid
flowchart LR
    subgraph Platforms["chat platforms"]
        direction TB
        Slack
        Telegram
        Teams
        WhatsApp
        Discord
    end

    Platforms -- "webhook / gateway" --> Connector["chatnec connector<br/>(FastAPI)"]
    Connector -- "UniversalMessage" --> Agent["your agent<br/>any framework, any language"]
    Agent -- "UniversalReply" --> Connector
    Connector -- "platform send API" --> Platforms
```

Two ways to plug an agent in:

| | Embedded | HTTP |
|---|---|---|
| Where it runs | Same process as the connector | Anywhere — any language, any host |
| Wiring | `create_app(handler=my_handler)` | `AGENT_MODE=http`, `AGENT_WEBHOOK_URL=...` |
| Contract | `async (UniversalMessage) -> str \| UniversalReply \| None` | POST body is `UniversalMessage` JSON, response is `{"text": "..."}` |
| Best for | Python agents, fastest setup | Node/Go/Java/etc. agents, or independent scaling |

The HTTP contract is deliberately the smallest possible surface, one JSON
request in and one JSON response out, so it never presupposes a framework.
The [TypeScript SDK](ts-sdk/) is a thin convenience wrapper around that same
contract for Node.

## Demo

[`docs/demo.md`](docs/demo.md) has a real captured terminal transcript of the
full webhook → agent → reply round trip running locally — including
per-conversation context persisting across turns — plus the test suite
passing. It uses a stand-in platform adapter so it's reproducible without
registering real bot credentials first; the code path exercised is identical
to the one the real platform adapters run.

## Quickstart — scaffold a project

```bash
pip install chatnec
chatnec init my-agent
cd my-agent
cp .env.example .env   # fill in credentials for the platform(s) you're using
uvicorn app:app --reload
```

`chatnec init` writes a starter `app.py` (an echo agent wired to every platform
you configure) plus an `.env.example` and `.gitignore` — edit one function to
call your real agent.

## Quickstart — Python, embedded

```bash
cd python
pip install -e .
cp env.example .env   # fill in TELEGRAM_BOT_TOKEN and/or SLACK_*/TEAMS_*/WHATSAPP_*/DISCORD_*
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
(`slack`, `telegram`, `teams`, or `whatsapp` — Discord connects itself, see
below) — see the comments in [`python/env.example`](python/env.example) for
per-platform setup notes.

## Quickstart — any language, HTTP mode

Run the connector standalone:

```bash
AGENT_MODE=http AGENT_WEBHOOK_URL=http://localhost:9000/agent \
  uvicorn examples.standalone_service:app --reload
```

Your agent, in whatever language or framework you like, just needs to answer
POSTs with `{"text": "..."}`. For Node.js, the TS SDK does this for you:

```ts
import { createAgentServer } from "@chatnec/sdk";

createAgentServer(async (message) => {
  return `You said: ${message.text}`; // swap in LangChain.js, Vercel AI SDK, etc.
}, { port: 9000 });
```

## Platform support

| Platform | Auth | Inbound | Notes |
|---|---|---|---|
| Slack | Bot token + signing secret | Webhook, HMAC-SHA256 signature | Handles the `url_verification` handshake automatically |
| Telegram | Bot token | Webhook, optional secret token | Includes a `register_webhook()` helper |
| Teams | Bot Framework app ID/password | Webhook, Bot Framework JWT validated against JWKS | OAuth2 client-credentials token cached for outbound sends |
| WhatsApp | Meta Cloud API access token | Webhook, HMAC-SHA256 signature + GET handshake | `pip install chatnec` (no extra needed) |
| Discord | Bot token | Gateway (persistent connection, not a webhook) | `pip install chatnec[discord]`; requires the Message Content privileged intent |

All outbound sends retry on 429/5xx with exponential backoff (honoring
`Retry-After`) — see [`chatnec/retry.py`](python/chatnec/retry.py).

## Framework examples

Same five-line pattern for any framework — call it, return text:

- [LangChain](python/examples/langchain_agent.py) / [`from_langchain_runnable`](python/chatnec/integrations/langchain.py)
- [CrewAI](python/examples/crewai_agent.py)
- [AutoGen](python/examples/autogen_agent.py)
- [OpenAI Assistants](python/examples/openai_assistants_agent.py)

## Production

- **Docker**: `docker build -t chatnec python/` or `docker compose up` (starts
  the connector + Redis — see [`docker-compose.yml`](docker-compose.yml))
- **Session state**: in-memory by default; set `REDIS_URL` to switch to
  `RedisSessionStore` so conversation state survives restarts and is shared
  across processes (`pip install chatnec[redis]`)
- **Metrics**: `GET /metrics` in Prometheus text format — messages received,
  replies sent, and agent errors, labeled by platform
- **Logging**: structured JSON to stdout by default (`LOG_FORMAT=text` for
  plain-text logs; `LOG_LEVEL` to adjust verbosity)
- **CI**: [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs the
  Python test suite, builds the TS SDK, and builds the Docker image on every
  push/PR

## Layout

```
python/chatnec/
  models.py            UniversalMessage, UniversalReply, AgentHandler
  adapters/             slack.py, telegram.py, teams.py, whatsapp.py, discord.py, base.py (add new platforms here)
  agent_connector.py    embedded vs HTTP dispatch to your agent
  server.py             FastAPI app: /webhook/{platform}, /reply, /health, /metrics
  integrations/         from_function (generic), from_langchain_runnable (example)
  session.py            per-conversation state (in-memory or Redis)
  retry.py              backoff for outbound platform API calls
  metrics.py            Prometheus-format counters
  logging_config.py     structured JSON logging
  cli.py                `chatnec init` project scaffolding
ts-sdk/src/              createAgentServer + ChatConnectorClient for Node agents
```

## Adding a new platform

Subclass `chatnec.adapters.base.PlatformAdapter` and implement `parse_webhook`
and `send_message`; register it in `_build_adapters_from_settings()` in
`server.py` (or just pass `adapters={...}` to `create_app()` directly). For a
platform with no inbound webhook (like Discord), set `is_push_adapter = True`
and implement `start_listening()` instead. See
[`docs/architecture.md`](docs/architecture.md) for the full message flow and
design rationale.

## Tests

```bash
cd python && pytest
```

## License

[MIT](LICENSE)
