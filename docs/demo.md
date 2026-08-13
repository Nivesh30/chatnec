# Demo: it working, end to end

This is a real captured transcript of the connector running locally — no mocked
output. It uses `python/examples/demo_fake_platform.py`, which stands in for a
real chat platform (so no Slack/Telegram/Teams credentials are needed to see the
full request flow), wired to a tiny stateful agent function via
`chatnec.integrations.from_function`.

The same code path — webhook in, `PlatformAdapter.parse_webhook`,
`AgentHandler`, `PlatformAdapter.send_message` — is exactly what runs for the
real Slack/Telegram/Teams adapters; only the adapter implementation differs.

## Running it yourself

```bash
cd python
pip install -e ".[dev]"
uvicorn examples.demo_fake_platform:app --port 8123
```

## 1. Health check

```
$ curl -s http://127.0.0.1:8123/health
{"status":"ok","platforms":["demo"]}
```

## 2. First message in a conversation

```
$ curl -s -X POST http://127.0.0.1:8123/webhook/demo \
    -H "Content-Type: application/json" \
    -d '{"chat_id":"chat-42","user_name":"Alice","text":"Hello, can you help me connect to Slack?"}'
{"received":1}
```

Server-side log (the demo adapter prints instead of calling a real chat API —
a real adapter would call `chat.postMessage` / `sendMessage` / the Bot Framework
Connector API here instead):

```
[demo bot -> chat chat-42]: (turn 1) You said: Hello, can you help me connect to Slack?
INFO:     127.0.0.1:55855 - "POST /webhook/demo HTTP/1.1" 200 OK
```

## 3. Second message, same conversation — context persists

```
$ curl -s -X POST http://127.0.0.1:8123/webhook/demo \
    -H "Content-Type: application/json" \
    -d '{"chat_id":"chat-42","user_name":"Alice","text":"Great, what about Telegram?"}'
{"received":1}
```

```
[demo bot -> chat chat-42]: (turn 2) You said: Great, what about Telegram?
INFO:     127.0.0.1:55856 - "POST /webhook/demo HTTP/1.1" 200 OK
```

`turn` incrementing from 1 to 2 for the same `chat_id` shows the per-conversation
session store (`chatnec.session`) round-tripping state through the agent
function across requests — this is what lets a plain stateless function behave
like a multi-turn conversation.

## Test suite

```
$ pytest -v
============================= test session starts =============================
platform win32 -- Python 3.12.2, pytest-9.1.1, pluggy-1.6.0
collected 8 items

tests/test_agent_connector.py::test_embedded_connector_with_plain_string_handler PASSED [ 12%]
tests/test_agent_connector.py::test_embedded_connector_returns_none_when_handler_returns_none PASSED [ 25%]
tests/test_agent_connector.py::test_from_function_wraps_sync_function PASSED [ 37%]
tests/test_agent_connector.py::test_from_function_persists_context_across_calls PASSED [ 50%]
tests/test_models.py::test_reply_to_inherits_addressing PASSED           [ 62%]
tests/test_models.py::test_message_defaults PASSED                       [ 75%]
tests/test_slack_adapter.py::test_verify_webhook_accepts_valid_signature PASSED [ 87%]
tests/test_slack_adapter.py::test_verify_webhook_rejects_bad_signature PASSED [100%]

============================== 8 passed in 1.05s ==============================
```

## Going from this demo to a real platform

Swap `adapters={"demo": DemoPlatformAdapter()}` for nothing (let
`create_app()` build adapters from environment variables) and set the relevant
credentials — see [`python/env.example`](../python/env.example) and the
per-platform notes in the main [README](../README.md#quickstart-python-embedded).
Once a real bot's webhook is pointed at `/webhook/slack` (or `telegram`/`teams`),
the flow captured above is identical, just with a real chat window on the other
end instead of a `curl` command and a print statement.

> Real Slack/Telegram/Teams screenshots aren't included yet because that
> requires registering a bot with each platform (an account-specific,
> credential-bearing step only you can do). Once you've registered one, this
> file is the place to drop the screenshot — happy to help wire it up.
