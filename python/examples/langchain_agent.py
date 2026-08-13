"""Wiring an existing LangChain AgentExecutor up to Slack/Telegram/Teams.
Requires: pip install chatnec[langchain]
"""
from langchain.agents import AgentExecutor  # your existing agent setup
from chatnec import create_app
from chatnec.integrations.langchain import from_langchain_runnable

agent_executor: AgentExecutor = ...  # build this however you already do

app = create_app(handler=from_langchain_runnable(agent_executor))
