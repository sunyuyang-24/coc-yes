from __future__ import annotations

import json
import logging
from collections import defaultdict
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

logger = logging.getLogger(__name__)


class RoomConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)
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
        # 快照连接列表，防止遍历时被其他协程修改
        connections = list(self._connections.get(room_id, []))
        stale: list[WebSocket] = []
        for websocket in connections:
            try:
                data = payload
                if store and payload.get("type") == "room_update" and "room" in payload:
                    member_id = self._member_map.get(websocket, "")
                    if member_id:
                        try:
                            sanitized = store.get_room_sanitized(payload["room"]["id"], member_id)
                            data = {"type": "room_update", "room": sanitized}
                        except Exception:
                            logger.exception("Failed to sanitize room data for broadcast; skipping this client")
                            continue
                await websocket.send_json(data)
            except (WebSocketDisconnect, RuntimeError):
                stale.append(websocket)
        # 批量清理断开连接
        for websocket in stale:
            self.disconnect(room_id, websocket)

    async def send_to(self, room_id: str, target_member_id: str, payload: dict) -> None:
        """向指定 member 发送消息（WebRTC 信令用）"""
        for websocket in list(self._connections.get(room_id, [])):
            mid = self._member_map.get(websocket, "")
            if mid == target_member_id:
                try:
                    await websocket.send_json(payload)
                except (WebSocketDisconnect, RuntimeError):
                    self.disconnect(room_id, websocket)
                return

    def get_online_members(self, room_id: str) -> list[str]:
        """获取房间在线成员 ID 列表"""
        return [
            self._member_map[ws]
            for ws in self._connections.get(room_id, [])
            if ws in self._member_map
        ]
