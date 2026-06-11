import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.limiter import limiter
from app.modules.bootstrap.router import router as bootstrap_router
from app.modules.health.router import router as health_router
from app.modules.rooms.router import router as rooms_router, room_socket, store
from app.modules.rules.router import router as rules_router
from fastapi import WebSocket


async def _cleanup_loop():
    """Periodically remove rooms that have been empty for >30 seconds."""
    while True:
        await asyncio.sleep(15)
        try:
            removed = store.cleanup_empty_rooms(max_idle_seconds=30)
            if removed:
                print(f"[cleanup] removed {removed} empty room(s)")
        except Exception:
            pass  # Don't crash the cleanup loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="Online Call of Cthulhu table assistant API.",
        redirect_slashes=False,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def rate_limit_middleware(request, call_next):
        # Skip WebSocket and health check from rate limiting
        if request.url.path.endswith("/ws") or request.url.path == "/api/health":
            return await call_next(request)
        await limiter(request)
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix="/api", tags=["health"])
    app.include_router(bootstrap_router, prefix="/api", tags=["bootstrap"])
    app.include_router(rooms_router, prefix="/api", tags=["rooms"])
    app.include_router(rules_router, prefix="/api", tags=["rules"])

    @app.websocket("/api/rooms/{room_id}/ws")
    async def ws_room(websocket: WebSocket, room_id: str, member_id: str = ""):
        await room_socket(websocket, room_id, member_id)

    return app


app = create_app()