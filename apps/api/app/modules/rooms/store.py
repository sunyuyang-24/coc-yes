from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import secrets
import string
from pathlib import Path
from threading import RLock
from uuid import uuid4


class RoomStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = RLock()
        self._state = self._load()

    def create_room(self, name: str, keeper_name: str) -> tuple[dict, str]:
        with self._lock:
            room_id = uuid4().hex[:12]
            keeper_id = uuid4().hex
            room = {
                "id": room_id,
                "name": name,
                "status": "preparing",
                "inviteCode": self._invite_code(),
                "createdAt": self._now(),
                "members": [
                    {
                        "id": keeper_id,
                        "displayName": keeper_name,
                        "role": "keeper",
                        "joinedAt": self._now(),
                        "online": False,
                    }
                ],
                "messages": [],
                "rolls": [],
            }

            self._state["rooms"][room_id] = room
            self._add_system_message(room, f"{keeper_name} 创建了房间。")
            self._save()
            return deepcopy(room), keeper_id

    def join_room(self, invite_code: str, display_name: str) -> tuple[dict, str]:
        with self._lock:
            room = self._find_by_invite(invite_code)
            member_id = uuid4().hex
            room["members"].append(
                {
                    "id": member_id,
                    "displayName": display_name,
                    "role": "player",
                    "joinedAt": self._now(),
                    "online": False,
                }
            )
            self._add_system_message(room, f"{display_name} 加入了房间。")
            self._save()
            return deepcopy(room), member_id

    def get_room(self, room_id: str) -> dict:
        with self._lock:
            return deepcopy(self._require_room(room_id))

    def add_message(self, room_id: str, sender_id: str, content: str) -> dict:
        with self._lock:
            room = self._require_room(room_id)
            sender = self._find_member(room, sender_id)
            message = {
                "id": uuid4().hex,
                "type": "text",
                "roomId": room_id,
                "senderId": sender_id,
                "senderName": sender["displayName"],
                "senderRole": sender["role"],
                "content": content,
                "createdAt": self._now(),
            }
            room["messages"].append(message)
            self._save()
            return deepcopy(message)

    def add_dice_roll(self, room_id: str, roller_id: str, roll: dict) -> dict:
        with self._lock:
            room = self._require_room(room_id)
            roller = self._find_member(room, roller_id)
            roll_record = {
                **roll,
                "id": uuid4().hex,
                "roomId": room_id,
                "rollerId": roller_id,
                "rollerName": roller["displayName"],
                "rollerRole": roller["role"],
                "createdAt": self._now(),
            }
            message = {
                "id": uuid4().hex,
                "type": "dice_roll",
                "roomId": room_id,
                "senderId": roller_id,
                "senderName": roller["displayName"],
                "senderRole": roller["role"],
                "content": self._format_roll_message(roll_record),
                "roll": roll_record,
                "createdAt": roll_record["createdAt"],
            }

            room.setdefault("rolls", []).append(roll_record)
            room["messages"].append(message)
            self._save()

            return deepcopy(roll_record)

    def set_member_online(self, room_id: str, member_id: str, online: bool) -> dict:
        with self._lock:
            room = self._require_room(room_id)
            member = self._find_member(room, member_id)
            member["online"] = online
            self._save()
            return deepcopy(room)

    def _add_system_message(self, room: dict, content: str) -> None:
        room["messages"].append(
            {
                "id": uuid4().hex,
                "type": "system",
                "roomId": room["id"],
                "senderId": None,
                "senderName": "系统",
                "senderRole": "system",
                "content": content,
                "createdAt": self._now(),
            }
        )

    def _load(self) -> dict:
        if not self.path.exists():
            return {"rooms": {}}

        with self.path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")

        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(self._state, file, ensure_ascii=False, indent=2)

        temp_path.replace(self.path)

    def _find_by_invite(self, invite_code: str) -> dict:
        normalized = invite_code.strip().upper()

        for room in self._state["rooms"].values():
            if room["inviteCode"] == normalized:
                return room

        raise KeyError("invite_not_found")

    def _require_room(self, room_id: str) -> dict:
        try:
            return self._state["rooms"][room_id]
        except KeyError as error:
            raise KeyError("room_not_found") from error

    def _find_member(self, room: dict, member_id: str) -> dict:
        for member in room["members"]:
            if member["id"] == member_id:
                return member

        raise KeyError("member_not_found")

    def _invite_code(self) -> str:
        alphabet = string.ascii_uppercase + string.digits
        existing = {room["inviteCode"] for room in self._state["rooms"].values()}

        while True:
            code = "".join(secrets.choice(alphabet) for _ in range(6))

            if code not in existing:
                return code

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _format_roll_message(self, roll: dict) -> str:
        label = f"「{roll['label']}」" if roll.get("label") else roll["expression"]
        result = f"{label} 投掷结果 {roll['total']}"

        if roll.get("successLabel"):
            result = f"{result}，{roll['successLabel']}"

        return result
