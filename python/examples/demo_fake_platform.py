"""Runnable demo used to produce the terminal transcript in docs/demo.md.

Simulates an inbound chat message through a minimal fake platform adapter (no
real Slack/Telegram credentials needed) so you can see the full
webhook -> agent -> reply round trip working end to end.
"""
from chatnec import create_app
from chatnec.adapters.base import PlatformAdapter
from chatnec.integrations import from_function
from chatnec.models import UniversalMessage, UniversalReply


class DemoPlatformAdapter(PlatformAdapter):
    """A stand-in for a real chat platform: turns a simple {"chat_id","text"}
    JSON body into a UniversalMessage, and prints replies instead of calling
    a real chat API.
    """

    name = "demo"

    async def parse_webhook(self, request):
        payload = await request.json()
        return [
            UniversalMessage(
                platform=self.name,
                chat_id=payload["chat_id"],
                user_id=payload.get("user_id", "demo-user"),
                user_name=payload.get("user_name", "Demo User"),
                text=payload["text"],
            )
        ]

    async def send_message(self, reply: UniversalReply) -> None:
        print(f"[demo bot -> chat {reply.chat_id}]: {reply.text}")


def my_agent(text: str, context: dict) -> str:
    turn = context.get("turn", 0) + 1
    context["turn"] = turn
    return f"(turn {turn}) You said: {text}"


app = create_app(
    handler=from_function(my_agent),
    adapters={"demo": DemoPlatformAdapter()},
)
