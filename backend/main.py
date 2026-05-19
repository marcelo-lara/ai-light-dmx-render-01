import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FIXTURES_DIR = Path("/app/fixtures")


def load_data() -> tuple[list, list]:
    fixtures = json.loads((FIXTURES_DIR / "fixtures.json").read_text())
    pois = json.loads((FIXTURES_DIR / "pois.json").read_text())
    return fixtures, pois


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        fixtures, pois = load_data()
        await websocket.send_json({"type": "init", "fixtures": fixtures, "pois": pois})

        # Keep connection alive with periodic pings
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=25.0)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
