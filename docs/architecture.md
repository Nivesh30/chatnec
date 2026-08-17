[← back to README](../README.md)

# Architecture

## Message flow — webhook platforms (Slack, Telegram, Teams, WhatsApp)

```
1. Platform sends a webhook POST (or, for WhatsApp's verification step, a GET)
   to /webhook/{platform}
2. PlatformAdapter.handle_handshake()  -- short-circuits platform verification
   handshakes (Slack's url_verification challenge, WhatsApp's hub.challenge)
3. PlatformAdapter.verify_webhook()    -- rejects unsigned/forged requests
4. PlatformAdapter.parse_webhook()     -- platform payload -> UniversalMessage[]
5. AgentConnector.handle(message)      -- routes to your agent, either:
     - EmbeddedAgentConnector: calls your in-process AgentHandler directly
     - HTTPAgentConnector: POSTs the UniversalMessage JSON to AGENT_WEBHOOK_URL
       and expects {"text": "..."} back
6. PlatformAdapter.send_message(reply) -- UniversalReply -> platform's send API
   (via chatnec.retry.send_with_retry: backs off on 429/5xx)
```

Steps 2–4 and 6 are platform-specific (one file per platform in
`chatnec/adapters/`); step 5 is platform-agnostic and is the only place your
agent code touches the system.

## Message flow — push platforms (Discord, Teams-as-you)

Discord has no inbound webhook for regular channel messages — only a
persistent Gateway (WebSocket) connection delivers those. Adapters for
platforms like this set `is_push_adapter = True` and implement
`start_listening(handle)` instead of `parse_webhook`/`verify_webhook`:

```
1. On app startup, the server calls adapter.start_listening(handle) as a
   background task for every push adapter (handle == AgentConnector.handle,
   wrapped to also call send_message on the reply)
2. The adapter drives its own message source and for each inbound message
   builds a UniversalMessage, then calls handle(msg)
3. On shutdown, the server calls adapter.stop_listening() and cancels the task
```

Same interface, two different message sources inside step 2:

- **`DiscordAdapter`**: opens a persistent Gateway (WebSocket) connection via
  discord.py and reacts to `on_message` events as they arrive.
- **`TeamsUserAdapter`**: no persistent connection or webhook fits Microsoft
  Graph's delegated-access model well, so it polls instead — every
  `poll_interval_seconds` it lists `/me/chats`, then for each chat calls
  `/chats/{id}/messages/delta` with the deltaLink saved from the previous
  poll (Graph's change-tracking mechanism, so each poll only returns messages
  since the last one, not the whole chat again). The very first poll for a
  chat is treated as priming: it captures a baseline deltaLink but doesn't
  dispatch anything, so restarting the connector doesn't replay a chat's
  entire history through your agent. Messages authored by the signed-in
  user themselves are filtered out to avoid echo loops, mirroring how
  `SlackAdapter`/`DiscordAdapter` ignore their own bot's messages.

This keeps the platform-specific transport (webhook vs. persistent connection
vs. polling) fully inside the adapter — `AgentConnector` and your agent code
never know the difference.

## Why a normalized message instead of per-platform webhooks

Slack, Telegram, Teams (bot), Teams (as you), WhatsApp, and Discord each have
distinct event payloads, auth schemes (HMAC signature vs. bot API secret
token vs. Bot Framework JWT vs. delegated OAuth2/MSAL vs. Gateway session),
and reply APIs (`chat.postMessage`, `sendMessage`, Bot Framework Connector
activities, Microsoft Graph, the Cloud API, Discord's REST API). An agent
that wants to run on all of them either reimplements this six times, or is
coupled to one platform's SDK. `UniversalMessage` / `UniversalReply`
(`chatnec/models.py`) exist so an agent is written once against one schema —
notably, `TeamsUserAdapter` proves the abstraction holds even for a
fundamentally different access model (acting as a user rather than as a bot):
the agent code is identical either way.

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
semantics.

`default_session_store()` picks the backing store: `RedisSessionStore` if
`REDIS_URL` is set (durable, shared across processes — keys expire after 30
days of inactivity by default), otherwise `InMemorySessionStore` (fine for a
single dev process, lost on restart). Implement the three-method
`SessionStore` protocol to back it with something else.

## Reliability and observability

- **Retries** (`chatnec/retry.py`): every adapter's `send_message` wraps its
  outbound HTTP call in `send_with_retry`, which retries 429/5xx responses and
  transport errors with exponential backoff, honoring a `Retry-After` header
  when the platform sends one.
- **Metrics** (`chatnec/metrics.py`): an in-process `Metrics` singleton counts
  `messages_received_total`, `replies_sent_total`, and `agent_errors_total`,
  each labeled by platform, rendered as Prometheus text at `GET /metrics`.
- **Logging** (`chatnec/logging_config.py`): structured JSON to stdout by
  default (`LOG_FORMAT=text` for plain text), configured once in
  `create_app()` from `LOG_LEVEL`/`LOG_FORMAT`.

## Webhook verification fails closed

`server.py` genuinely enforces `PlatformAdapter.verify_webhook()` — a `False`
return is a `401`, not advisory. `SlackAdapter` and `WhatsAppAdapter` return
`False` (reject) when their signing secret isn't configured, rather than the
more permissive "accept everything, verification is opt-in" default a generic
`PlatformAdapter` base class uses. That distinction matters here specifically:
Slack and WhatsApp are documented, internet-facing webhook receivers by
design, and a webhook silently accepted without verification feeds directly
into the agent pipeline and can trigger outbound sends using the bot's real
credentials — a misconfiguration (bot token set, signing secret forgotten)
should produce a loud, obvious failure (every webhook request 401s, logged at
startup) rather than a silent authentication bypass. `TeamsAdapter` defaults
`verify_jwt=True` for the same reason; it's only meant to be disabled for
local testing against the Bot Framework Emulator.

## Async replies

Some agents do long-running work and can't reply synchronously within the
webhook response (or, for Discord, within the Gateway event handler). `POST
/reply` lets an agent push a `UniversalReply` back at any later time, and the
connector routes it through the correct platform adapter's `send_message`.
This endpoint requires `REPLY_API_KEY` — unlike per-platform webhook
verification, there's no way to derive an equivalent signature check for an
arbitrary caller, so the fail-closed behavior here is simpler: no key
configured means the endpoint is off (`503`), not open.

## Adding a platform

Implement `chatnec.adapters.base.PlatformAdapter`:

```python
class PlatformAdapter(ABC):
    async def parse_webhook(self, request: Request) -> list[UniversalMessage]: ...
    async def send_message(self, reply: UniversalReply) -> None: ...
    async def verify_webhook(self, request, body) -> bool: ...       # optional, default: accept all
    async def handle_handshake(self, request, body) -> Response | None: ...  # optional

    # For push-style platforms only (no inbound webhook — e.g. Discord's Gateway):
    is_push_adapter: bool = False
    async def start_listening(self, handle: MessageHandler) -> None: ...
    async def stop_listening(self) -> None: ...
```

Register it either in `_build_adapters_from_settings()` in `server.py` (env-var
driven, matches the others) or by passing `adapters={"my-platform": ...}`
directly to `create_app()`.
