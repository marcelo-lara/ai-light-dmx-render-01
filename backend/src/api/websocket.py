import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.config import FIXTURES_JSON, POIS_JSON

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Tracks active WebSocket clients and broadcasts JSON payloads to all of them."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    def add(self, ws: WebSocket) -> None:
        self._clients.add(ws)

    def remove(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    def __bool__(self) -> bool:
        return bool(self._clients)

    async def broadcast(self, payload: dict) -> None:
        disconnected: set[WebSocket] = set()
        for ws in self._clients:
            try:
                await ws.send_json(payload)
            except Exception:
                disconnected.add(ws)
        for ws in disconnected:
            self._clients.discard(ws)


def _load_init_data() -> dict:
    fixtures = json.loads(FIXTURES_JSON.read_text())
    pois = json.loads(POIS_JSON.read_text())
    return {"type": "init", "fixtures": fixtures, "pois": pois}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    manager: ConnectionManager = websocket.app.state.manager
    await websocket.accept()
    manager.add(websocket)
    try:
        await websocket.send_json(_load_init_data())
        # Hold connection open; frames arrive via the broadcast loop in lifespan.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.remove(websocket)
