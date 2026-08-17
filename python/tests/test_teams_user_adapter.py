from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from chatnec.adapters.teams_user import TeamsUserAdapter, _strip_html
from chatnec.models import UniversalMessage, UniversalReply


def _resp(json_body: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json=json_body, request=httpx.Request("GET", "http://test"))


def test_strip_html_removes_tags_and_unescapes_entities():
    assert _strip_html("<p>Hi &amp; welcome</p>") == "Hi & welcome"


@pytest.fixture
def adapter(monkeypatch):
    a = TeamsUserAdapter(client_id="client-id")
    a._me_id = "me-id"
    monkeypatch.setattr(a, "_headers", AsyncMock(return_value={"Authorization": "Bearer fake"}))
    return a


@pytest.mark.asyncio
async def test_priming_poll_does_not_dispatch_history(adapter, monkeypatch):
    handle = AsyncMock(return_value=None)
    get = AsyncMock(
        return_value=_resp(
            {
                "value": [
                    {
                        "messageType": "message",
                        "from": {"user": {"id": "other-user", "displayName": "Alice"}},
                        "body": {"content": "old message"},
                    }
                ],
                "@odata.deltaLink": "https://graph.microsoft.com/v1.0/chats/c1/messages/delta?token=abc",
            }
        )
    )
    monkeypatch.setattr(adapter._client, "get", get)

    await adapter._poll_chat("c1", {"Authorization": "Bearer fake"}, handle)

    handle.assert_not_called()
    assert adapter._delta_links["c1"] == "https://graph.microsoft.com/v1.0/chats/c1/messages/delta?token=abc"


@pytest.mark.asyncio
async def test_second_poll_dispatches_new_messages(adapter, monkeypatch):
    adapter._delta_links["c1"] = "https://graph.microsoft.com/v1.0/chats/c1/messages/delta?token=abc"
    handle = AsyncMock(return_value=None)
    get = AsyncMock(
        return_value=_resp(
            {
                "value": [
                    {
                        "messageType": "message",
                        "from": {"user": {"id": "other-user", "displayName": "Alice"}},
                        "body": {"content": "<p>hello there</p>"},
                    }
                ],
                "@odata.deltaLink": "https://graph.microsoft.com/v1.0/chats/c1/messages/delta?token=def",
            }
        )
    )
    monkeypatch.setattr(adapter._client, "get", get)

    await adapter._poll_chat("c1", {"Authorization": "Bearer fake"}, handle)

    handle.assert_awaited_once()
    dispatched: UniversalMessage = handle.call_args[0][0]
    assert dispatched.text == "hello there"
    assert dispatched.user_id == "other-user"
    assert dispatched.chat_id == "c1"
    assert adapter._delta_links["c1"] == "https://graph.microsoft.com/v1.0/chats/c1/messages/delta?token=def"


@pytest.mark.asyncio
async def test_ignores_own_messages(adapter, monkeypatch):
    adapter._delta_links["c1"] = "https://graph.microsoft.com/v1.0/chats/c1/messages/delta?token=abc"
    handle = AsyncMock(return_value=None)
    get = AsyncMock(
        return_value=_resp(
            {
                "value": [
                    {
                        "messageType": "message",
                        "from": {"user": {"id": "me-id", "displayName": "Me"}},
                        "body": {"content": "my own message"},
                    }
                ],
                "@odata.deltaLink": "https://graph.microsoft.com/v1.0/chats/c1/messages/delta?token=def",
            }
        )
    )
    monkeypatch.setattr(adapter._client, "get", get)

    await adapter._poll_chat("c1", {"Authorization": "Bearer fake"}, handle)

    handle.assert_not_called()


@pytest.mark.asyncio
async def test_reply_sent_when_handler_returns_one(adapter, monkeypatch):
    adapter._delta_links["c1"] = "https://graph.microsoft.com/v1.0/chats/c1/messages/delta?token=abc"
    reply = UniversalReply(platform="teams_user", chat_id="c1", text="a reply")
    handle = AsyncMock(return_value=reply)
    get = AsyncMock(
        return_value=_resp(
            {
                "value": [
                    {
                        "messageType": "message",
                        "from": {"user": {"id": "other-user", "displayName": "Alice"}},
                        "body": {"content": "hi"},
                    }
                ],
                "@odata.deltaLink": "https://graph.microsoft.com/v1.0/chats/c1/messages/delta?token=def",
            }
        )
    )
    monkeypatch.setattr(adapter._client, "get", get)
    send_message = AsyncMock()
    monkeypatch.setattr(adapter, "send_message", send_message)

    await adapter._poll_chat("c1", {"Authorization": "Bearer fake"}, handle)

    send_message.assert_awaited_once_with(reply)


@pytest.mark.asyncio
async def test_send_message_posts_to_chat(adapter, monkeypatch):
    post = AsyncMock(return_value=httpx.Response(201, request=httpx.Request("POST", "http://test")))
    monkeypatch.setattr(adapter._client, "post", post)

    await adapter.send_message(UniversalReply(platform="teams_user", chat_id="c1", text="hello"))

    post.assert_awaited_once()
    args, kwargs = post.call_args
    assert args[0] == "/chats/c1/messages"
    assert kwargs["json"] == {"body": {"content": "hello"}}
