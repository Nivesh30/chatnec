"""The standalone connector service. Run with:

    uvicorn chatnec.server:app --host 0.0.0.0 --port 8000

Configure via environment variables (see chatnec.config.Settings) or by building
`app` yourself with `create_app(...)` for embedded mode.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse

from .adapters.base import PlatformAdapter
from .adapters.discord import DiscordAdapter
from .adapters.slack import SlackAdapter
from .adapters.teams import TeamsAdapter
from .adapters.teams_user import TeamsUserAdapter
from .adapters.telegram import TelegramAdapter
from .adapters.whatsapp import WhatsAppAdapter
from .agent_connector import EmbeddedAgentConnector, HTTPAgentConnector
from .config import settings
from .logging_config import configure_logging
from .metrics import metrics
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
    configure_logging(settings.log_level, json_format=settings.log_format == "json")

    active_adapters = adapters if adapters is not None else _build_adapters_from_settings()
    if not active_adapters:
        logger.warning("No platform adapters configured — set credentials in the environment.")

    if handler is not None:
        connector = EmbeddedAgentConnector(handler)
    elif settings.agent_webhook_url:
        connector = HTTPAgentConnector(settings.agent_webhook_url, settings.agent_timeout_seconds)
    else:
        connector = None  # agent will push replies asynchronously via POST /reply

    push_adapters = {name: a for name, a in active_adapters.items() if a.is_push_adapter}
    webhook_adapters = {name: a for name, a in active_adapters.items() if not a.is_push_adapter}
    push_tasks: list[asyncio.Task] = []

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        for name, adapter in push_adapters.items():
            logger.info("chatnec: starting push adapter '%s'", name)
            push_tasks.append(asyncio.create_task(_run_push_adapter(name, adapter, connector)))
        yield
        for adapter in push_adapters.values():
            await adapter.stop_listening()
        for task in push_tasks:
            task.cancel()

    app = FastAPI(title="chatnec", version="0.1.0", lifespan=lifespan)

    app.state.adapters = active_adapters
    app.state.connector = connector

    @app.post("/webhook/{platform}")
    async def webhook_post(platform: str, request: Request):
        return await _handle_webhook(platform, request, webhook_adapters, connector)

    @app.get("/webhook/{platform}")
    async def webhook_get(platform: str, request: Request):
        """Some platforms verify a webhook with a GET handshake (e.g. WhatsApp's
        hub.challenge) rather than the POST used for actual events."""
        adapter = webhook_adapters.get(platform)
        if adapter is None:
            raise HTTPException(status_code=404, detail=f"No adapter configured for '{platform}'")

        response = await adapter.handle_handshake(request, b"")
        if response is not None:
            return response
        raise HTTPException(status_code=404)

    @app.post("/reply")
    async def reply(payload: UniversalReply, x_api_key: Optional[str] = Header(default=None)):
        """Lets an agent running elsewhere push a reply back asynchronously
        (e.g. after long-running work), instead of returning it synchronously
        from its webhook response.
        """
        if not settings.reply_api_key:
            # Fail closed: with no key configured this endpoint would otherwise let
            # anyone send arbitrary messages using this bot's real credentials.
            raise HTTPException(status_code=503, detail="REPLY_API_KEY is not configured")
        if x_api_key != settings.reply_api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")

        adapter = active_adapters.get(payload.platform)
        if adapter is None:
            raise HTTPException(status_code=404, detail=f"No adapter configured for '{payload.platform}'")

        await adapter.send_message(payload)
        metrics.inc("replies_sent_total", payload.platform)
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"status": "ok", "platforms": list(active_adapters.keys())}

    @app.get("/metrics")
    async def metrics_endpoint():
        return PlainTextResponse(metrics.render_prometheus())

    return app


async def _handle_webhook(
    platform: str,
    request: Request,
    webhook_adapters: dict[str, PlatformAdapter],
    connector,
):
    adapter = webhook_adapters.get(platform)
    if adapter is None:
        raise HTTPException(status_code=404, detail=f"No adapter configured for '{platform}'")

    body = await request.body()

    handshake_response = await adapter.handle_handshake(request, body)
    if handshake_response is not None:
        return handshake_response

    if not await adapter.verify_webhook(request, body):
        raise HTTPException(status_code=401, detail="Webhook verification failed")

    messages = await adapter.parse_webhook(request)

    for message in messages:
        await _handle_message(message, adapter, connector)

    return {"received": len(messages)}


async def _handle_message(message, adapter: Optional[PlatformAdapter], connector) -> Optional[UniversalReply]:
    metrics.inc("messages_received_total", message.platform)
    logger.info(
        "chatnec: message received",
        extra={"chatnec_platform": message.platform, "chatnec_chat_id": message.chat_id},
    )

    if connector is None:
        return None  # no agent wired up — caller consumes messages some other way

    try:
        reply = await connector.handle(message)
    except Exception:
        metrics.inc("agent_errors_total", message.platform)
        logger.exception("chatnec: agent handler failed for message %s", message.id)
        return None

    if reply is not None and adapter is not None:
        await adapter.send_message(reply)
        metrics.inc("replies_sent_total", message.platform)

    return reply


async def _run_push_adapter(name: str, adapter: PlatformAdapter, connector) -> None:
    async def handle(message):
        return await _handle_message(message, adapter, connector)

    try:
        await adapter.start_listening(handle)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("chatnec: push adapter '%s' crashed", name)


def _build_adapters_from_settings() -> dict[str, PlatformAdapter]:
    adapters: dict[str, PlatformAdapter] = {}

    if settings.slack_bot_token:
        adapters["slack"] = SlackAdapter(settings.slack_bot_token, settings.slack_signing_secret)

    if settings.telegram_bot_token:
        adapters["telegram"] = TelegramAdapter(settings.telegram_bot_token)

    if settings.teams_app_id and settings.teams_app_password:
        adapters["teams"] = TeamsAdapter(settings.teams_app_id, settings.teams_app_password)

    if settings.teams_user_client_id:
        adapters["teams_user"] = TeamsUserAdapter(
            settings.teams_user_client_id,
            settings.teams_user_tenant_id,
            settings.teams_user_poll_interval_seconds,
            settings.teams_user_token_cache_path,
        )

    if settings.whatsapp_access_token and settings.whatsapp_phone_number_id:
        adapters["whatsapp"] = WhatsAppAdapter(
            settings.whatsapp_access_token,
            settings.whatsapp_phone_number_id,
            settings.whatsapp_app_secret,
            settings.whatsapp_verify_token,
        )

    if settings.discord_bot_token:
        adapters["discord"] = DiscordAdapter(settings.discord_bot_token)

    return adapters


# Default app instance for `uvicorn chatnec.server:app`. Uses HTTP agent mode
# (settings.agent_webhook_url) since no in-process handler can be passed on the CLI.
app = create_app()
