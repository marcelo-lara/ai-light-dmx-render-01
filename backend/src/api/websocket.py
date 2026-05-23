import json
import logging
from collections.abc import Iterable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.config import POIS_JSON
from src.dmx.artnet_core import artnet_node
from src.simulation.ball import create_simulator

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
def _serialize_settings(app) -> dict:
    return {
        "sim_mode": app.state.sim_mode,
        "ball_speed": app.state.ball_speed,
        "dmx_output_enabled": app.state.dmx_output_enabled,
        "active_poi_id": app.state.ball.active_poi_id,
    }


def _load_init_data_from_app(app) -> dict:
    pois = json.loads(POIS_JSON.read_text())
    return {
        "type": "init",
        "fixtures": [f.to_dict() for f in app.state.fixtures],
        "pois": pois,
        **_serialize_settings(app),
    }


def _build_universe_frame(fixtures: Iterable) -> bytearray:
    universe = bytearray(512)
    for fixture in fixtures:
        start = fixture.base_channel - 1
        data = fixture.to_dmx_buffer()
        end = min(start + len(data), len(universe))
        universe[start:end] = data[: end - start]
    return universe


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
        await websocket.send_json(_load_init_data_from_app(websocket.app))
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                continue

            if msg.get("type") == "set_sim_mode":
                mode = msg.get("mode")
                if mode in ("3d", "floor", "poi"):
                    websocket.app.state.sim_mode = mode
                    websocket.app.state.ball = create_simulator(
                        mode,
                        websocket.app.state.ball_speed,
                        websocket.app.state.pois,
                    )
                    await manager.broadcast({"type": "settings", **_serialize_settings(websocket.app)})
                continue

            if msg.get("type") == "set_ball_speed":
                try:
                    speed = float(msg.get("speed"))
                except (TypeError, ValueError):
                    continue
                websocket.app.state.ball_speed = max(0.1, min(4.0, speed))
                websocket.app.state.ball.set_speed_multiplier(websocket.app.state.ball_speed)
                await manager.broadcast({"type": "settings", **_serialize_settings(websocket.app)})
                continue

            if msg.get("type") == "set_dmx_output":
                enabled = bool(msg.get("enabled"))
                if websocket.app.state.dmx_output_enabled and not enabled:
                    artnet_node.send_frame(bytearray(512), universe=0, source="system")
                websocket.app.state.dmx_output_enabled = enabled
                artnet_node.set_output_enabled(enabled)
                await manager.broadcast({"type": "settings", **_serialize_settings(websocket.app)})
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
                    artnet_node.send_frame(
                        _build_universe_frame(websocket.app.state.fixtures),
                        universe=0,
                        source="sender",
                    )
                except (KeyError, ValueError) as exc:
                    logger.debug("set_fixture ignored: %s", exc)

    except WebSocketDisconnect:
        pass
    finally:
        manager.remove(websocket)
