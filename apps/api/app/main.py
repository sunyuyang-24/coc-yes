import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from starlette.requests import Request
from starlette.types import ASGIApp, Scope, Receive, Send

from app.core.auth_middleware import AuthMiddleware
from app.core.config import settings
from app.core.db import init_db as init_database, close_db
from app.core.limiter import limiter
from app.modules.auth.router import router as auth_router
from app.modules.bootstrap.router import router as bootstrap_router
from app.modules.health.router import router as health_router
from app.modules.rooms.router import router as rooms_router, room_socket
from app.modules.rooms.router_combat import router as combat_router
from app.modules.rooms.router_chase import router as chase_router
from app.modules.rooms.router_coc import router as coc_router
from app.modules.rooms.deps import store
from app.modules.rules.router import router as rules_router


class RateLimitMiddleware:
    """Pure ASGI middleware that passes WebSocket connections through."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive=receive)
        if request.url.path == "/api/health":
            await self.app(scope, receive, send)
            return
        try:
            await limiter(request)
        except Exception:
            response = PlainTextResponse("Too Many Requests", status_code=429)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


async def _cleanup_loop():
    while True:
        await asyncio.sleep(300)  # check every 5 minutes
        try:
            # Only removes abandoned "preparing" rooms idle for >1 hour
            removed = store.cleanup_empty_rooms(max_idle_seconds=3600)
            if removed:
                print(f"[cleanup] removed {removed} abandoned preparing room(s)")
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database(settings.data_dir)
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()
    close_db()


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Online Call of Cthulhu table assistant API.",
    redirect_slashes=False,
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(bootstrap_router, prefix="/api", tags=["bootstrap"])
app.include_router(rooms_router, prefix="/api", tags=["rooms"])
app.include_router(combat_router, prefix="/api", tags=["combat"])
app.include_router(chase_router, prefix="/api", tags=["chase"])
app.include_router(coc_router, prefix="/api", tags=["coc"])
app.include_router(rules_router, prefix="/api", tags=["rules"])


@app.websocket("/api/rooms/{room_id}/ws")
async def ws_room(websocket: WebSocket, room_id: str, member_id: str = ""):
    await room_socket(websocket, room_id, member_id)