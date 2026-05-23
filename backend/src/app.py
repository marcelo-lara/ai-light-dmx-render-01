import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.websocket import ConnectionManager
from src.config import FIXTURES_JSON, FRAME_INTERVAL
from src.dmx.models.fixtures import load_all as _load_fixtures
from src.simulation.ball import BallSimulator, FloorBallSimulator

logger = logging.getLogger(__name__)


async def _frame_loop(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(FRAME_INTERVAL)
        app.state.ball.tick()
        if app.state.manager:
            fixture_states = {
                f.id: {"color_hex": f.color_hex, "intensity": f.intensity}
                for f in app.state.fixtures
            }
            await app.state.manager.broadcast(
                {
                    "type": "frame",
                    "ball": app.state.ball.position(),
                    "sim_mode": app.state.sim_mode,
                    "fixture_states": fixture_states,
                }
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.manager = ConnectionManager()
    app.state.sim_mode = "3d"
    app.state.ball = BallSimulator()
    app.state.fixtures = _load_fixtures(str(FIXTURES_JSON))

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
