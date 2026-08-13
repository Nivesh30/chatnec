from fastapi.testclient import TestClient

from chatnec import create_app
from chatnec.adapters.base import PlatformAdapter
from chatnec.integrations import from_function
from chatnec.models import UniversalMessage, UniversalReply


class FakeAdapter(PlatformAdapter):
    name = "fake"

    def __init__(self):
        self.sent: list[str] = []

    async def parse_webhook(self, request):
        payload = await request.json()
        return [
            UniversalMessage(platform="fake", chat_id=payload["chat_id"], user_id="u1", text=payload["text"])
        ]

    async def send_message(self, reply: UniversalReply) -> None:
        self.sent.append(reply.text)


def _client(handler):
    fake = FakeAdapter()
    app = create_app(handler=handler, adapters={"fake": fake})
    return TestClient(app), fake


def test_health_reports_configured_platforms():
    client, _ = _client(from_function(lambda text: text))
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "platforms": ["fake"]}


def test_webhook_round_trip_delivers_reply():
    client, fake = _client(from_function(lambda text: f"echo: {text}"))
    resp = client.post("/webhook/fake", json={"chat_id": "c1", "text": "hi"})
    assert resp.status_code == 200
    assert resp.json() == {"received": 1}
    assert fake.sent == ["echo: hi"]


def test_webhook_unknown_platform_404s():
    client, _ = _client(from_function(lambda text: text))
    resp = client.post("/webhook/nope", json={"chat_id": "c1", "text": "hi"})
    assert resp.status_code == 404


def test_metrics_endpoint_reflects_traffic():
    client, _ = _client(from_function(lambda text: f"echo: {text}"))
    client.post("/webhook/fake", json={"chat_id": "c1", "text": "hi"})

    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert 'chatnec_messages_received_total{platform="fake"} 1' in resp.text
    assert 'chatnec_replies_sent_total{platform="fake"} 1' in resp.text


def test_agent_error_is_counted_and_does_not_500():
    def broken(text: str) -> str:
        raise ValueError("boom")

    client, fake = _client(from_function(broken))
    resp = client.post("/webhook/fake", json={"chat_id": "c1", "text": "hi"})

    assert resp.status_code == 200
    assert fake.sent == []
    assert 'chatnec_agent_errors_total{platform="fake"} 1' in client.get("/metrics").text
