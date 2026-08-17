import json
import sys

import pytest

from chatnec.integrations.cli_agent import from_cli_agent
from chatnec.models import UniversalMessage


def _msg(text: str = "hi") -> UniversalMessage:
    return UniversalMessage(platform="fake", chat_id="c1", user_id="u1", text=text)


@pytest.mark.asyncio
async def test_runs_command_and_returns_stripped_stdout():
    def command(text, context):
        return [sys.executable, "-c", f"print({text!r})"]

    handler = from_cli_agent(command)

    result = await handler(_msg("hello"))

    assert result == "hello"


@pytest.mark.asyncio
async def test_output_parser_transforms_result():
    def command(text, context):
        payload = json.dumps({"result": text.upper()})
        return [sys.executable, "-c", f"print({payload!r})"]

    def parse(output, context):
        return json.loads(output)["result"]

    handler = from_cli_agent(command, output_parser=parse)

    result = await handler(_msg("hi"))

    assert result == "HI"


@pytest.mark.asyncio
async def test_context_mutation_in_output_parser_persists_across_turns():
    seen_context_on_second_call = {}

    def command(text, context):
        seen_context_on_second_call.update(context)
        payload = "resumed" if context.get("session_id") else "fresh"
        return [sys.executable, "-c", f"print({payload!r})"]

    def parse(output, context):
        context["session_id"] = "abc123"
        return output.strip()

    handler = from_cli_agent(command, output_parser=parse)

    first = await handler(_msg())
    second = await handler(_msg())

    assert first == "fresh"
    assert second == "resumed"
    assert seen_context_on_second_call.get("session_id") == "abc123"


@pytest.mark.asyncio
async def test_timeout_is_handled_gracefully():
    def command(text, context):
        return [sys.executable, "-c", "import time; time.sleep(5)"]

    handler = from_cli_agent(command, timeout_seconds=0.2)

    result = await handler(_msg())

    assert "too long" in result.lower()


@pytest.mark.asyncio
async def test_nonzero_exit_returns_friendly_error():
    def command(text, context):
        return [sys.executable, "-c", "import sys; sys.exit(1)"]

    handler = from_cli_agent(command)

    result = await handler(_msg())

    assert "wrong" in result.lower()


@pytest.mark.asyncio
async def test_context_includes_message_metadata():
    seen = {}

    def command(text, context):
        seen.update(context)
        return [sys.executable, "-c", "print('ok')"]

    handler = from_cli_agent(command)
    msg = UniversalMessage(platform="slack", chat_id="c1", user_id="u1", user_name="Alice", text="hi")

    await handler(msg)

    assert seen["platform"] == "slack"
    assert seen["user_id"] == "u1"
    assert seen["user_name"] == "Alice"
