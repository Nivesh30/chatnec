[← back to README](../README.md)

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

## 4. Metrics after those two requests

```
$ curl -s http://127.0.0.1:8123/metrics
# HELP chatnec_messages_received_total Inbound messages parsed from a platform webhook or push connection.
# TYPE chatnec_messages_received_total counter
chatnec_messages_received_total{platform="demo"} 2
# HELP chatnec_replies_sent_total Replies successfully delivered back to a platform.
# TYPE chatnec_replies_sent_total counter
chatnec_replies_sent_total{platform="demo"} 2
# HELP chatnec_agent_errors_total Agent handler invocations that raised an exception.
# TYPE chatnec_agent_errors_total counter
```

## Test suite

```
$ pytest -v
============================= test session starts =============================
platform win32 -- Python 3.12.2, pytest-9.1.1, pluggy-1.6.0
collected 28 items

tests/test_agent_connector.py::test_embedded_connector_with_plain_string_handler PASSED
tests/test_agent_connector.py::test_embedded_connector_returns_none_when_handler_returns_none PASSED
tests/test_agent_connector.py::test_from_function_wraps_sync_function PASSED
tests/test_agent_connector.py::test_from_function_persists_context_across_calls PASSED
tests/test_cli.py::test_init_project_creates_expected_files PASSED
tests/test_cli.py::test_init_project_does_not_overwrite_existing_files PASSED
tests/test_cli.py::test_main_init_via_argv PASSED
tests/test_metrics.py::test_inc_and_render PASSED
tests/test_metrics.py::test_render_includes_all_known_counters_even_when_empty PASSED
tests/test_models.py::test_reply_to_inherits_addressing PASSED
tests/test_models.py::test_message_defaults PASSED
tests/test_retry.py::test_returns_immediately_on_success PASSED
tests/test_retry.py::test_retries_on_retryable_status_then_succeeds PASSED
tests/test_retry.py::test_gives_up_after_max_attempts PASSED
tests/test_retry.py::test_does_not_retry_non_retryable_status PASSED
tests/test_retry.py::test_retries_on_transport_error_then_raises PASSED
tests/test_server.py::test_health_reports_configured_platforms PASSED
tests/test_server.py::test_webhook_round_trip_delivers_reply PASSED
tests/test_server.py::test_webhook_unknown_platform_404s PASSED
tests/test_server.py::test_metrics_endpoint_reflects_traffic PASSED
tests/test_server.py::test_agent_error_is_counted_and_does_not_500 PASSED
tests/test_slack_adapter.py::test_verify_webhook_accepts_valid_signature PASSED
tests/test_slack_adapter.py::test_verify_webhook_rejects_bad_signature PASSED
tests/test_whatsapp_adapter.py::test_verify_webhook_accepts_valid_signature PASSED
tests/test_whatsapp_adapter.py::test_verify_webhook_rejects_bad_signature PASSED
tests/test_whatsapp_adapter.py::test_handshake_returns_challenge_on_valid_verify_token PASSED
tests/test_whatsapp_adapter.py::test_handshake_rejects_wrong_verify_token PASSED
tests/test_whatsapp_adapter.py::test_parse_webhook_extracts_text_messages PASSED

============================== 28 passed in 1.24s ==============================
```

## Going from this demo to a real platform

Swap `adapters={"demo": DemoPlatformAdapter()}` for nothing (let
`create_app()` build adapters from environment variables) and set the relevant
credentials — see [`python/env.example`](../python/env.example) and the
per-platform notes in the main [README](../README.md#quickstart-python-embedded).
Once a real bot's webhook is pointed at `/webhook/slack` (or `telegram`/`teams`/`whatsapp`;
Discord connects itself via its Gateway, no webhook needed), the flow captured
above is identical, just with a real chat window on the other end instead of a
`curl` command and a print statement.

> Real Slack/Telegram/Teams/WhatsApp/Discord screenshots aren't included yet
> because that requires registering a bot with each platform (an
> account-specific, credential-bearing step only you can do). Once you've
> registered one, this file is the place to drop the screenshot — happy to
> help wire it up.
