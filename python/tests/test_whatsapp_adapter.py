import hashlib
import hmac

import pytest
from fastapi import Request

from chatnec.adapters.whatsapp import WhatsAppAdapter


def _make_request(body: bytes, headers: dict[str, str] | None = None, query_string: bytes = b"", method: str = "POST") -> Request:
    scope = {
        "type": "http",
        "method": method,
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "query_string": query_string,
    }
    request = Request(scope)

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request._receive = receive  # type: ignore[attr-defined]
    return request


@pytest.mark.asyncio
async def test_verify_webhook_accepts_valid_signature():
    secret = "app-secret"
    adapter = WhatsAppAdapter(access_token="t", phone_number_id="p", app_secret=secret)

    body = b'{"object":"whatsapp_business_account"}'
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    request = _make_request(body, {"X-Hub-Signature-256": signature})

    assert await adapter.verify_webhook(request, body) is True


@pytest.mark.asyncio
async def test_verify_webhook_rejects_bad_signature():
    adapter = WhatsAppAdapter(access_token="t", phone_number_id="p", app_secret="app-secret")
    body = b'{"object":"whatsapp_business_account"}'
    request = _make_request(body, {"X-Hub-Signature-256": "sha256=bad"})

    assert await adapter.verify_webhook(request, body) is False


@pytest.mark.asyncio
async def test_verify_webhook_fails_closed_when_no_secret_configured():
    adapter = WhatsAppAdapter(access_token="t", phone_number_id="p")  # no app_secret
    body = b'{"object":"whatsapp_business_account"}'
    signature = "sha256=" + hmac.new(b"some-secret", body, hashlib.sha256).hexdigest()
    request = _make_request(body, {"X-Hub-Signature-256": signature})

    assert await adapter.verify_webhook(request, body) is False


@pytest.mark.asyncio
async def test_handshake_returns_challenge_on_valid_verify_token():
    adapter = WhatsAppAdapter(access_token="t", phone_number_id="p", verify_token="secret-token")
    query = b"hub.mode=subscribe&hub.verify_token=secret-token&hub.challenge=12345"
    request = _make_request(b"", query_string=query, method="GET")

    response = await adapter.handle_handshake(request, b"")

    assert response is not None
    assert response.status_code == 200
    assert response.body == b"12345"


@pytest.mark.asyncio
async def test_handshake_rejects_wrong_verify_token():
    adapter = WhatsAppAdapter(access_token="t", phone_number_id="p", verify_token="secret-token")
    query = b"hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=12345"
    request = _make_request(b"", query_string=query, method="GET")

    response = await adapter.handle_handshake(request, b"")

    assert response is not None
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_parse_webhook_extracts_text_messages():
    adapter = WhatsAppAdapter(access_token="t", phone_number_id="p")
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": "15551234567", "profile": {"name": "Alice"}}],
                            "messages": [
                                {"from": "15551234567", "type": "text", "text": {"body": "hi there"}}
                            ],
                        }
                    }
                ]
            }
        ]
    }
    request = _make_request(b"{}")

    async def fake_json():
        return payload

    request.json = fake_json  # type: ignore[method-assign]

    messages = await adapter.parse_webhook(request)

    assert len(messages) == 1
    assert messages[0].chat_id == "15551234567"
    assert messages[0].user_name == "Alice"
    assert messages[0].text == "hi there"
