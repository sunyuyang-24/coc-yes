import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from starlette.requests import Request
from starlette.types import ASGIApp, Scope, Receive, Send

from app.core.config import settings
from app.core.limiter import limiter
from app.modules.bootstrap.router import router as bootstrap_router
from app.modules.health.router import router as health_router
from app.modules.rooms.router import router as rooms_router, room_socket, store
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
        await asyncio.sleep(15)
        try:
            removed = store.cleanup_empty_rooms(max_idle_seconds=300)
            if removed:
                print(f"[cleanup] removed {removed} empty room(s)")
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Online Call of Cthulhu table assistant API.",
    redirect_slashes=False,
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware)
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