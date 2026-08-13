import hashlib
import hmac
import time

import pytest
from fastapi import Request

from chatnec.adapters.slack import SlackAdapter


def _make_request(body: bytes, headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    request = Request(scope)

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request._receive = receive  # type: ignore[attr-defined]
    return request


@pytest.mark.asyncio
async def test_verify_webhook_accepts_valid_signature():
    secret = "test-secret"
    adapter = SlackAdapter(bot_token="xoxb-fake", signing_secret=secret)

    body = b'{"type":"event_callback"}'
    timestamp = str(int(time.time()))
    base = f"v0:{timestamp}:{body.decode()}".encode()
    signature = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()

    request = _make_request(
        body,
        {"X-Slack-Request-Timestamp": timestamp, "X-Slack-Signature": signature},
    )

    assert await adapter.verify_webhook(request, body) is True


@pytest.mark.asyncio
async def test_verify_webhook_rejects_bad_signature():
    adapter = SlackAdapter(bot_token="xoxb-fake", signing_secret="test-secret")
    body = b'{"type":"event_callback"}'
    request = _make_request(
        body,
        {"X-Slack-Request-Timestamp": str(int(time.time())), "X-Slack-Signature": "v0=bad"},
    )

    assert await adapter.verify_webhook(request, body) is False
