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

    # --- Microsoft Teams (Bot Framework) ---
    teams_app_id: Optional[str] = None
    teams_app_password: Optional[str] = None

    # --- Agent integration ---
    # "embedded": handler runs in this same process (see chatnec.embed)
    # "http": connector POSTs each UniversalMessage to agent_webhook_url and expects a reply
    agent_mode: Literal["embedded", "http"] = "embedded"
    agent_webhook_url: Optional[str] = None
    agent_timeout_seconds: float = 30.0

    # Shared secret the connector expects on inbound /reply calls when agents reply asynchronously.
    reply_api_key: Optional[str] = None


settings = Settings()
