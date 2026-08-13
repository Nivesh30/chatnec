"""Wiring a CrewAI crew up to Slack/Telegram/Teams/WhatsApp.
Requires: pip install chatnec[crewai]

Same pattern as every other framework: crew.kickoff() takes inputs and
returns text, so from_function's plain (text, context) signature covers it —
no chatnec-specific CrewAI integration module needed.
"""
from crewai import Crew  # your existing crew setup
from chatnec import create_app
from chatnec.integrations import from_function

crew: Crew = ...  # build this however you already do


def run_crew(text: str, context: dict) -> str:
    result = crew.kickoff(inputs={"query": text, **context})
    return str(result)


app = create_app(handler=from_function(run_crew))
