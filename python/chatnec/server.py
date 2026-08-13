"""The standalone connector service. Run with:

    uvicorn chatnec.server:app --host 0.0.0.0 --port 8000

Configure via environment variables (see chatnec.config.Settings) or by building
`app` yourself with `create_app(...)` for embedded mode.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request

from .adapters.base import PlatformAdapter
from .adapters.slack import SlackAdapter
from .adapters.teams import TeamsAdapter
from .adapters.telegram import TelegramAdapter
from .agent_connector import EmbeddedAgentConnector, HTTPAgentConnector
from .config import settings
from .models import AgentHandler, UniversalReply

logger = logging.getLogger("chatnec")


def create_app(
    handler: Optional[AgentHandler] = None,
    adapters: Optional[dict[str, PlatformAdapter]] = None,
) -> FastAPI:
    """Build the connector service.

    - `handler`: an in-process AgentHandler. If omitted, falls back to HTTP mode
      using settings.agent_webhook_url.
    - `adapters`: override which platform adapters are active. If omitted, adapters
      are built from environment settings (only platforms with credentials set are enabled).
    """
    app = FastAPI(title="chatnec", version="0.1.0")

    active_adapters = adapters if adapters is not None else _build_adapters_from_settings()
    if not active_adapters:
        logger.warning("No platform adapters configured — set credentials in the environment.")

    if handler is not None:
        connector = EmbeddedAgentConnector(handler)
    elif settings.agent_webhook_url:
        connector = HTTPAgentConnector(settings.agent_webhook_url, settings.agent_timeout_seconds)
    else:
        connector = None  # agent will push replies asynchronously via POST /reply

    app.state.adapters = active_adapters
    app.state.connector = connector

    @app.post("/webhook/{platform}")
    async def webhook(platform: str, request: Request):
        adapter = active_adapters.get(platform)
        if adapter is None:
            raise HTTPException(status_code=404, detail=f"No adapter configured for '{platform}'")

        body = await request.body()

        handshake_response = await adapter.handle_handshake(request, body)
        if handshake_response is not None:
            return handshake_response

        if not await adapter.verify_webhook(request, body):
            raise HTTPException(status_code=401, detail="Webhook verification failed")

        messages = await adapter.parse_webhook(request)

        if connector is None:
            # No agent wired up — caller is responsible for consuming messages some other way.
            return {"received": len(messages)}

        for message in messages:
            try:
                reply = await connector.handle(message)
            except Exception:
                logger.exception("Agent handler failed for message %s", message.id)
                continue
            if reply is not None:
                await adapter.send_message(reply)

        return {"received": len(messages)}

    @app.post("/reply")
    async def reply(payload: UniversalReply, x_api_key: Optional[str] = Header(default=None)):
        """Lets an agent running elsewhere push a reply back asynchronously
        (e.g. after long-running work), instead of returning it synchronously
        from its webhook response.
        """
        if settings.reply_api_key and x_api_key != settings.reply_api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")

        adapter = active_adapters.get(payload.platform)
        if adapter is None:
            raise HTTPException(status_code=404, detail=f"No adapter configured for '{payload.platform}'")

        await adapter.send_message(payload)
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"status": "ok", "platforms": list(active_adapters.keys())}

    return app


def _build_adapters_from_settings() -> dict[str, PlatformAdapter]:
    adapters: dict[str, PlatformAdapter] = {}

    if settings.slack_bot_token:
        adapters["slack"] = SlackAdapter(settings.slack_bot_token, settings.slack_signing_secret)

    if settings.telegram_bot_token:
        adapters["telegram"] = TelegramAdapter(settings.telegram_bot_token)

    if settings.teams_app_id and settings.teams_app_password:
        adapters["teams"] = TeamsAdapter(settings.teams_app_id, settings.teams_app_password)

    return adapters


# Default app instance for `uvicorn chatnec.server:app`. Uses HTTP agent mode
# (settings.agent_webhook_url) since no in-process handler can be passed on the CLI.
app = create_app()
