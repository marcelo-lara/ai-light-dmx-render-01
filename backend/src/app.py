import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.websocket import ConnectionManager
from src.config import FRAME_INTERVAL
from src.simulation.ball import BallSimulator

logger = logging.getLogger(__name__)


async def _frame_loop(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(FRAME_INTERVAL)
        app.state.ball.tick()
        if app.state.manager:
            await app.state.manager.broadcast(
                {"type": "frame", "ball": app.state.ball.position()}
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.manager = ConnectionManager()
    app.state.ball = BallSimulator()

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
