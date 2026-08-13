"""Simplest possible agent: any function `(text) -> str` becomes a bot on every
configured platform. Run:

    export TELEGRAM_BOT_TOKEN=...          # and/or SLACK_BOT_TOKEN + SLACK_SIGNING_SECRET
    uvicorn examples.embedded_mode:app --reload
"""
from chatnec import create_app
from chatnec.integrations import from_function


def my_agent(text: str) -> str:
    return f"You said: {text}"


app = create_app(handler=from_function(my_agent))
