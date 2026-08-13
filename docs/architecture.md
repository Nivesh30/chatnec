# Architecture

## Message flow

```
1. Platform sends a webhook POST to /webhook/{platform}
2. PlatformAdapter.handle_handshake()  -- short-circuits platform verification
   handshakes (e.g. Slack's url_verification challenge)
3. PlatformAdapter.verify_webhook()    -- rejects unsigned/forged requests
4. PlatformAdapter.parse_webhook()     -- platform payload -> UniversalMessage[]
5. AgentConnector.handle(message)      -- routes to your agent, either:
     - EmbeddedAgentConnector: calls your in-process AgentHandler directly
     - HTTPAgentConnector: POSTs the UniversalMessage JSON to AGENT_WEBHOOK_URL
       and expects {"text": "..."} back
6. PlatformAdapter.send_message(reply) -- UniversalReply -> platform's send API
```

Steps 2–4 and 6 are platform-specific (one file per platform in
`chatnec/adapters/`); step 5 is platform-agnostic and is the only place your
agent code touches the system.

## Why a normalized message instead of per-platform webhooks

Slack, Telegram, and Teams each have distinct event payloads, auth schemes
(HMAC signature vs. bot API secret token vs. Bot Framework JWT), and reply
APIs (`chat.postMessage`, `sendMessage`, Bot Framework Connector activities).
An agent that wants to run on all three either reimplements this three times,
or is coupled to one platform's SDK. `UniversalMessage` / `UniversalReply`
(`chatnec/models.py`) exist so an agent is written once against one schema.

## Two integration modes

| | Embedded | HTTP |
|---|---|---|
| Where the agent runs | Same process as the connector | Anywhere — any language, any host |
| How it's wired | `create_app(handler=my_handler)` | `AGENT_MODE=http`, `AGENT_WEBHOOK_URL=...` |
| Contract | `async (UniversalMessage) -> str \| UniversalReply \| None` | POST body is `UniversalMessage` JSON, response body is `{"text": "..."}` |
| Best for | Python agents, simplest setup | Node/Go/Java/etc. agents, or agents you want to scale/deploy independently |

The HTTP contract is deliberately the smallest possible surface — one JSON
request in, one JSON response out — specifically so it doesn't presuppose any
particular agent framework. The TypeScript SDK (`ts-sdk/`) is just a thin
convenience wrapper around that same contract for Node.

## Conversations and state

Platforms don't agree on what "a conversation" is (channel vs. DM vs. thread
vs. topic). `chatnec.session.conversation_key(platform, chat_id, thread_id)`
gives one consistent key so `chatnec.integrations.from_function` can hand your
plain function a per-conversation `context` dict that persists across turns,
without your agent code needing to know about platform-specific thread
semantics. The default store is in-memory (`InMemorySessionStore`); implement
the three-method `SessionStore` protocol to back it with Redis, a database,
etc. for multi-process deployments.

## Async replies

Some agents do long-running work and can't reply synchronously within the
webhook response. `POST /reply` (optionally behind `REPLY_API_KEY`) lets an
agent push a `UniversalReply` back at any later time, and the connector routes
it through the correct platform adapter's `send_message`.

## Adding a platform

Implement `chatnec.adapters.base.PlatformAdapter`:

```python
class PlatformAdapter(ABC):
    async def parse_webhook(self, request: Request) -> list[UniversalMessage]: ...
    async def send_message(self, reply: UniversalReply) -> None: ...
    async def verify_webhook(self, request, body) -> bool: ...       # optional, default: accept all
    async def handle_handshake(self, request, body) -> Response | None: ...  # optional
```

Register it either in `_build_adapters_from_settings()` in `server.py` (env-var
driven, matches the other three) or by passing `adapters={"discord": ...}`
directly to `create_app()`.
