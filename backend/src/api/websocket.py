import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.config import FIXTURES_JSON, POIS_JSON
from src.dmx.models.fixtures import load_all as _load_fixtures
from src.simulation.ball import BallSimulator, FloorBallSimulator

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
    fixtures = [f.to_dict() for f in _load_fixtures(str(FIXTURES_JSON))]
    pois = json.loads(POIS_JSON.read_text())
    return {"type": "init", "fixtures": fixtures, "pois": pois}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    manager: ConnectionManager = websocket.app.state.manager
    # Build a per-connection lookup so set_fixture commands can reach fixtures
    # that live on app.state (the same live objects the frame loop reads).
    fixtures_by_id: dict = {
        f.id: f for f in websocket.app.state.fixtures
    }
    await websocket.accept()
    manager.add(websocket)
    try:
        await websocket.send_json(_load_init_data())
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                continue

            if msg.get("type") == "set_sim_mode":
                mode = msg.get("mode")
                if mode in ("3d", "floor"):
                    websocket.app.state.sim_mode = mode
                    websocket.app.state.ball = (
                        BallSimulator() if mode == "3d" else FloorBallSimulator()
                    )
                continue

            if msg.get("type") == "set_fixture":
                fixture = fixtures_by_id.get(msg.get("id"))
                if fixture is None:
                    continue
                meta_key = msg.get("meta_key")
                value = msg.get("value")
                if meta_key is None or value is None:
                    continue
                # JSON arrays arrive as list; fixture.set() for rgb accepts any iterable,
                # but we normalise to tuple for clarity.
                if isinstance(value, list):
                    value = tuple(value)
                try:
                    fixture.set(meta_key, value)
                except (KeyError, ValueError) as exc:
                    logger.debug("set_fixture ignored: %s", exc)

    except WebSocketDisconnect:
        pass
    finally:
        manager.remove(websocket)
