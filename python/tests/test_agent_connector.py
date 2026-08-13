import pytest

from chatnec.agent_connector import EmbeddedAgentConnector
from chatnec.integrations import from_function
from chatnec.models import UniversalMessage, UniversalReply


@pytest.mark.asyncio
async def test_embedded_connector_with_plain_string_handler():
    async def handler(message: UniversalMessage) -> str:
        return f"echo: {message.text}"

    connector = EmbeddedAgentConnector(handler)
    msg = UniversalMessage(platform="slack", chat_id="C1", user_id="U1", text="hi")

    reply = await connector.handle(msg)

    assert isinstance(reply, UniversalReply)
    assert reply.text == "echo: hi"
    assert reply.chat_id == "C1"


@pytest.mark.asyncio
async def test_embedded_connector_returns_none_when_handler_returns_none():
    async def handler(message: UniversalMessage):
        return None

    connector = EmbeddedAgentConnector(handler)
    msg = UniversalMessage(platform="slack", chat_id="C1", user_id="U1", text="hi")

    assert await connector.handle(msg) is None


@pytest.mark.asyncio
async def test_from_function_wraps_sync_function():
    def agent(text: str) -> str:
        return text.upper()

    handler = from_function(agent)
    msg = UniversalMessage(platform="telegram", chat_id="1", user_id="2", text="hi")

    result = await handler(msg)

    assert result == "HI"


@pytest.mark.asyncio
async def test_from_function_persists_context_across_calls():
    def agent(text: str, context: dict) -> str:
        count = context.get("count", 0) + 1
        context["count"] = count
        return f"turn {count}"

    handler = from_function(agent)
    msg = UniversalMessage(platform="telegram", chat_id="1", user_id="2", text="hi")

    assert await handler(msg) == "turn 1"
    assert await handler(msg) == "turn 2"
