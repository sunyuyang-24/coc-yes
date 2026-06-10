from __future__ import annotations

from collections import defaultdict
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


class RoomConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, room_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[room_id].append(websocket)

    def disconnect(self, room_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(room_id, [])

        if websocket in connections:
            connections.remove(websocket)

        if not connections and room_id in self._connections:
            del self._connections[room_id]

    async def broadcast(self, room_id: str, payload: dict) -> None:
        stale: list[WebSocket] = []

        for websocket in list(self._connections.get(room_id, [])):
            try:
                await websocket.send_json(payload)
            except WebSocketDisconnect:
                stale.append(websocket)
            except RuntimeError:
                stale.append(websocket)

        for websocket in stale:
            self.disconnect(room_id, websocket)
