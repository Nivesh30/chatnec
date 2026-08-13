"""Microsoft Teams adapter via the Azure Bot Framework Connector REST API.

Auth notes:
- Outbound (sending messages) uses an OAuth2 client-credentials token from Azure AD,
  cached until near expiry.
- Inbound requests carry a bearer JWT issued by the Bot Framework. Full validation
  requires checking the signature against Bot Framework's JWKS and validating
  issuer/audience/appid. This adapter does that when `verify_jwt=True` (default);
  set it to False only for local testing against the Bot Framework Emulator.
"""
from __future__ import annotations

import time
from typing import Any, Optional

import httpx
from fastapi import Request

from ..models import UniversalMessage, UniversalReply
from ..retry import send_with_retry
from .base import PlatformAdapter

LOGIN_URL = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
OPENID_METADATA_URL = "https://login.botframework.com/v1/.well-known/openidconfiguration"
BOT_FRAMEWORK_SCOPE = "https://api.botframework.com/.default"


class TeamsAdapter(PlatformAdapter):
    name = "teams"

    def __init__(self, app_id: str, app_password: str, verify_jwt: bool = True) -> None:
        self.app_id = app_id
        self.app_password = app_password
        self.verify_jwt = verify_jwt
        self._client = httpx.AsyncClient(timeout=15.0)
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0
        self._jwks_cache: Optional[dict] = None

    async def _get_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        resp = await self._client.post(
            LOGIN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.app_id,
                "client_secret": self.app_password,
                "scope": BOT_FRAMEWORK_SCOPE,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expiry = time.time() + int(data.get("expires_in", 3600))
        return self._token

    async def verify_webhook(self, request: Request, body: bytes) -> bool:
        if not self.verify_jwt:
            return True

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False
        token = auth_header.removeprefix("Bearer ")

        try:
            import jwt
            from jwt import PyJWKClient
        except ImportError:
            raise RuntimeError(
                "Teams inbound JWT verification requires PyJWT and cryptography: "
                "pip install chatnec[teams]"
            )

        if self._jwks_cache is None:
            meta_resp = await self._client.get(OPENID_METADATA_URL)
            meta_resp.raise_for_status()
            self._jwks_cache = meta_resp.json()

        jwks_uri = self._jwks_cache["jwks_uri"]
        jwk_client = PyJWKClient(jwks_uri)
        signing_key = jwk_client.get_signing_key_from_jwt(token)

        try:
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.app_id,
                issuer="https://api.botframework.com",
            )
        except jwt.PyJWTError:
            return False

        return claims.get("appid") == self.app_id or claims.get("azp") == self.app_id

    async def parse_webhook(self, request: Request) -> list[UniversalMessage]:
        payload: dict[str, Any] = await request.json()
        if payload.get("type") != "message":
            return []

        conversation = payload.get("conversation", {})
        from_user = payload.get("from", {})

        return [
            UniversalMessage(
                platform=self.name,
                chat_id=conversation.get("id", ""),
                user_id=from_user.get("id", "unknown"),
                user_name=from_user.get("name"),
                text=payload.get("text", ""),
                metadata={
                    "service_url": payload.get("serviceUrl"),
                    "reply_to_id": payload.get("id"),
                    "recipient": payload.get("recipient"),
                    "from": from_user,
                    "conversation": conversation,
                },
                raw=payload,
            )
        ]

    async def send_message(self, reply: UniversalReply) -> None:
        service_url = reply.metadata.get("service_url")
        if not service_url:
            raise ValueError(
                "UniversalReply.metadata['service_url'] is required for Teams "
                "(copy it from the inbound message's metadata)"
            )

        token = await self._get_token()
        activity = {
            "type": "message",
            "text": reply.text,
            "from": reply.metadata.get("recipient"),
            "recipient": reply.metadata.get("from"),
            "conversation": {"id": reply.chat_id},
            "replyToId": reply.metadata.get("reply_to_id"),
        }
        url = f"{service_url.rstrip('/')}/v3/conversations/{reply.chat_id}/activities"
        resp = await send_with_retry(
            lambda: self._client.post(url, json=activity, headers={"Authorization": f"Bearer {token}"})
        )
        resp.raise_for_status()
