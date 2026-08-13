"""Run the connector as its own service, decoupled from the agent process — the
agent can be written in any language and just needs to expose one HTTP endpoint.

    export AGENT_MODE=http
    export AGENT_WEBHOOK_URL=http://localhost:9000/agent
    export TELEGRAM_BOT_TOKEN=...
    uvicorn examples.standalone_service:app --reload

Your agent's /agent endpoint receives a UniversalMessage JSON body and should
respond with {"text": "..."}.
"""
from chatnec import create_app

# No `handler` passed: falls back to settings.agent_webhook_url (HTTP mode).
app = create_app()
