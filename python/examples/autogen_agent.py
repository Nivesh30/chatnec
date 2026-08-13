"""Wiring an AutoGen ConversableAgent up to Slack/Telegram/Teams/WhatsApp.
Requires: pip install chatnec[autogen]

`context` (persisted per-conversation by chatnec) holds the running AutoGen
message history, so multi-turn conversations stay coherent per chat/thread.
"""
import autogen  # your existing agent config
from chatnec import create_app
from chatnec.integrations import from_function

assistant = autogen.ConversableAgent(
    name="assistant",
    llm_config={"config_list": [{"model": "gpt-4o-mini"}]},  # use your existing config
)


async def run_autogen(text: str, context: dict) -> str:
    history = context.setdefault("history", [])
    history.append({"role": "user", "content": text})

    reply = await assistant.a_generate_reply(messages=history)
    reply_text = reply["content"] if isinstance(reply, dict) else str(reply)

    history.append({"role": "assistant", "content": reply_text})
    return reply_text


app = create_app(handler=from_function(run_autogen))
