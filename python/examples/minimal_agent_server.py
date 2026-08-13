"""A toy 'agent' in its own process, speaking only plain HTTP — no chatnec
dependency at all. Pairs with standalone_service.py (AGENT_MODE=http).

    uvicorn examples.minimal_agent_server:app --port 9000
"""
from fastapi import FastAPI, Request

app = FastAPI()


@app.post("/agent")
async def handle_message(request: Request):
    message = await request.json()
    return {"text": f"Echo from agent process: {message['text']}"}
