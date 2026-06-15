import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.websocket import ConnectionManager
from src.config import FIXTURES_JSON, FRAME_INTERVAL, POIS_JSON
from src.dmx.artnet_core import artnet_node
from src.dmx.models.fixtures import load_all as _load_fixtures
from src.simulation.ball import create_simulator
from src.spatial.aim import TrilinearInterpolationStrategy, is_ref_poi_id

logger = logging.getLogger(__name__)


def _build_universe_frame(fixtures) -> bytearray:
    universe = bytearray(512)
    for fixture in fixtures:
        start = fixture.base_channel - 1
        data = fixture.to_dmx_buffer()
        end = min(start + len(data), len(universe))
        universe[start:end] = data[: end - start]
    return universe


def _apply_simulation_to_fixtures(app: FastAPI) -> None:
    ball_position = app.state.ball.position()
    moving_head_dim = max(64, min(255, round(96 + (ball_position["z"] * 159))))

    for fixture in app.state.fixtures:
        if fixture.fixture_type != "moving_head":
            continue

        pan, tilt = app.state.aim_strategy.aim_to_dmx(
            fixture,
            ball_position,
        )
        fixture.set("pan", pan)
        fixture.set("tilt", tilt)

        if fixture.has_channel("dim"):
            fixture.set("dim", moving_head_dim)


async def _frame_loop(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(FRAME_INTERVAL)
        if app.state.automation_enabled:
            app.state.ball.tick()
            _apply_simulation_to_fixtures(app)

        artnet_node.send_frame(
            _build_universe_frame(app.state.fixtures),
            source="system",
        )

        if app.state.manager:
            fixture_states = {
                f.id: {"color_hex": f.color_hex, "intensity": f.intensity}
                for f in app.state.fixtures
            }
            await app.state.manager.broadcast(
                {
                    "type": "frame",
                    "ball": app.state.ball.position(),
                    "active_poi_id": app.state.ball.active_poi_id,
                    "sim_mode": app.state.sim_mode,
                    "fixture_states": fixture_states,
                }
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.manager = ConnectionManager()
    app.state.sim_mode = "3d"
    app.state.ball_speed = 1.0
    app.state.automation_enabled = True
    app.state.dmx_output_enabled = False
    app.state.pois = json.loads(POIS_JSON.read_text())
    app.state.fixtures = _load_fixtures(str(FIXTURES_JSON))
    
    app.state.aim_strategy = TrilinearInterpolationStrategy()
    ref_pois = [p for p in app.state.pois if is_ref_poi_id(p.get("id", ""))]
    for fixture in app.state.fixtures:
        if fixture.fixture_type == "moving_head":
            app.state.aim_strategy.calibrate(fixture, ref_pois)

    app.state.ball = create_simulator(app.state.sim_mode, app.state.ball_speed, 
app.state.pois)

    task = asyncio.create_task(_frame_loop(app))
    logger.info("Frame loop started at %d FPS", round(1 / FRAME_INTERVAL))
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def create_app() -> FastAPI:
    from src.api import health_router, ws_router

    app = FastAPI(lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(ws_router)

    return app
