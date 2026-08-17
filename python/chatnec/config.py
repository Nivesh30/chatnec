"""Environment-driven configuration. Only credentials for platforms you set are activated."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Slack ---
    slack_bot_token: Optional[str] = None
    slack_signing_secret: Optional[str] = None

    # --- Telegram ---
    telegram_bot_token: Optional[str] = None

    # --- Microsoft Teams (Bot Framework — a separate bot identity added to conversations) ---
    teams_app_id: Optional[str] = None
    teams_app_password: Optional[str] = None

    # --- Microsoft Teams, acting as you (delegated Microsoft Graph — see
    # adapters/teams_user.py and `chatnec teams-login`) ---
    teams_user_client_id: Optional[str] = None
    teams_user_tenant_id: str = "common"
    teams_user_token_cache_path: Optional[str] = None
    teams_user_poll_interval_seconds: float = 15.0

    # --- WhatsApp (Meta Cloud API) ---
    whatsapp_access_token: Optional[str] = None
    whatsapp_phone_number_id: Optional[str] = None
    whatsapp_app_secret: Optional[str] = None
    whatsapp_verify_token: Optional[str] = None

    # --- Discord (Gateway, push-style — see adapters/discord.py) ---
    discord_bot_token: Optional[str] = None

    # --- Agent integration ---
    # "embedded": handler runs in this same process (see chatnec.embed)
    # "http": connector POSTs each UniversalMessage to agent_webhook_url and expects a reply
    agent_mode: Literal["embedded", "http"] = "embedded"
    agent_webhook_url: Optional[str] = None
    agent_timeout_seconds: float = 30.0

    # Shared secret the connector expects on inbound /reply calls when agents reply asynchronously.
    reply_api_key: Optional[str] = None

    # --- Session state ---
    # If set, chatnec.session.default_session_store() returns a RedisSessionStore
    # instead of the in-memory default (needed once you run more than one process).
    redis_url: Optional[str] = None

    # --- Observability ---
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"


settings = Settings()
