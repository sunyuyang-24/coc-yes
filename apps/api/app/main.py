from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.modules.bootstrap.router import router as bootstrap_router
from app.modules.health.router import router as health_router
from app.modules.rooms.router import router as rooms_router, room_socket
from app.modules.rules.router import router as rules_router
from fastapi import WebSocket


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="Online Call of Cthulhu table assistant API.",
    )

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