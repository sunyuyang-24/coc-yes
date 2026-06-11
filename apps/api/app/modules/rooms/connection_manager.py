from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


class RoomConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)
        # 记录每个连接的 member_id
        self._member_map: dict[WebSocket, str] = {}

    async def connect(self, room_id: str, websocket: WebSocket, member_id: str = "") -> None:
        await websocket.accept()
        self._connections[room_id].append(websocket)
        self._member_map[websocket] = member_id

    def disconnect(self, room_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(room_id, [])

        if websocket in connections:
            connections.remove(websocket)

        if not connections and room_id in self._connections:
            del self._connections[room_id]

        self._member_map.pop(websocket, None)

    async def broadcast(self, room_id: str, payload: dict, store=None) -> None:
        """广播房间更新。如果提供 store，则对每个连接按角色过滤数据。"""
        stale: list[WebSocket] = []

        for websocket in list(self._connections.get(room_id, [])):
            try:
                data = payload
                if store and payload.get("type") == "room_update" and "room" in payload:
                    member_id = self._member_map.get(websocket, "")
                    if member_id:
                        try:
                            sanitized = store.get_room_sanitized(payload["room"]["id"], member_id)
                            data = {"type": "room_update", "room": sanitized}
                        except Exception:
                            pass  # 降级：发送原始数据
                await websocket.send_json(data)
            except WebSocketDisconnect:
                stale.append(websocket)
            except RuntimeError:
                stale.append(websocket)

        for websocket in stale:
            self.disconnect(room_id, websocket)
