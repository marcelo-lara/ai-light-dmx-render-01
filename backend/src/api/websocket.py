import json
import logging
from collections.abc import Iterable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.dmx.artnet_core import artnet_node
from src.poi_store import persist_pois, persist_ref_coordinates
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
        "automation_enabled": app.state.automation_enabled,
        "dmx_output_enabled": app.state.dmx_output_enabled,
        "active_poi_id": app.state.ball.active_poi_id,
    }


def _load_init_data_from_app(app) -> dict:
    return {
        "type": "init",
        "fixtures": [f.to_dict() for f in app.state.fixtures],
        "pois": [*app.state.pois, *app.state.virtual_pois, *app.state.ref_pois],
        **_serialize_settings(app),
    }


def _persist_poi_targets(app, poi_id: str, fixture_targets: dict[str, dict[str, int]]) -> list[dict] | None:
    target_collection_name = None
    persisted_collection = None

    for collection_name in ("pois", "ref_pois"):
        collection = getattr(app.state, collection_name)
        updated = False
        next_pois: list[dict] = []

        for poi in collection:
            if poi.get("id") != poi_id:
                next_poi = poi
            else:
                current_targets = dict(poi.get("fixtures", {}))
                for fixture_id, target in fixture_targets.items():
                    current_targets[fixture_id] = {
                        "pan": int(target["pan"]),
                        "tilt": int(target["tilt"]),
                    }
                next_poi = {
                    **poi,
                    "fixtures": current_targets,
                }
                updated = True
            next_pois.append(next_poi)

        if updated:
            setattr(app.state, collection_name, next_pois)
            target_collection_name = collection_name
            persisted_collection = next_pois
            break

    if target_collection_name is None or persisted_collection is None:
        return None

    if target_collection_name == "pois":
        persist_pois(persisted_collection)
    else:
        persist_ref_coordinates(persisted_collection)

    return [*app.state.pois, *app.state.virtual_pois, *app.state.ref_pois]


def _build_universe_frame(fixtures: Iterable) -> bytearray:
    universe = bytearray(512)
    for fixture in fixtures:
        start = fixture.base_channel - 1
        data = fixture.to_dmx_buffer()
        end = min(start + len(data), len(universe))
        universe[start:end] = data[: end - start]
    return universe


def _all_runtime_pois(app) -> list[dict]:
    return [*app.state.pois, *app.state.virtual_pois]


def _aim_fixtures_to_location(app, location: dict[str, float]) -> None:
    for fixture in app.state.fixtures:
        if fixture.fixture_type != "moving_head":
            continue

        pan, tilt = app.state.aim_strategy.aim_to_dmx(fixture, location)
        fixture.set("pan", pan)
        fixture.set("tilt", tilt)


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
                        _all_runtime_pois(websocket.app),
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

            if msg.get("type") == "set_automation_enabled":
                websocket.app.state.automation_enabled = bool(msg.get("enabled"))
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
                continue

            if msg.get("type") == "save_poi_targets":
                poi_id = msg.get("poi_id")
                fixture_targets = msg.get("fixture_targets")
                if not isinstance(poi_id, str) or not isinstance(fixture_targets, dict):
                    continue
                try:
                    persisted_pois = _persist_poi_targets(websocket.app, poi_id, fixture_targets)
                except (TypeError, ValueError, KeyError) as exc:
                    logger.debug("save_poi_targets ignored: %s", exc)
                    continue
                if persisted_pois is not None:
                    await manager.broadcast({"type": "pois_updated", "pois": persisted_pois})
                continue

            if msg.get("type") == "aim_at_location":
                location = msg.get("location")
                if not isinstance(location, dict):
                    continue
                try:
                    target_location = {
                        "x": float(location["x"]),
                        "y": float(location["y"]),
                        "z": float(location["z"]),
                    }
                except (KeyError, TypeError, ValueError):
                    continue

                websocket.app.state.automation_enabled = False
                _aim_fixtures_to_location(websocket.app, target_location)
                artnet_node.send_frame(
                    _build_universe_frame(websocket.app.state.fixtures),
                    universe=0,
                    source="sender",
                )
                await manager.broadcast({"type": "settings", **_serialize_settings(websocket.app)})
                continue

    except WebSocketDisconnect:
        pass
    finally:
        manager.remove(websocket)
