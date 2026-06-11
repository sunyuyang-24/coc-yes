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
                "characters": [],
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

    def create_npc(self, room_id: str, keeper_id: str, name: str) -> dict:
        character = {
            "basic": {"name": name, "occupation": "NPC"},
            "attributes": [
                {"key": "STR", "label": "??", "value": 50, "half": 25, "fifth": 10},
                {"key": "DEX", "label": "??", "value": 50, "half": 25, "fifth": 10},
                {"key": "POW", "label": "??", "value": 50, "half": 25, "fifth": 10},
                {"key": "CON", "label": "??", "value": 50, "half": 25, "fifth": 10},
                {"key": "APP", "label": "??", "value": 50, "half": 25, "fifth": 10},
                {"key": "EDU", "label": "??", "value": 50, "half": 25, "fifth": 10},
                {"key": "SIZ", "label": "??", "value": 50, "half": 25, "fifth": 10},
                {"key": "INT", "label": "??", "value": 50, "half": 25, "fifth": 10},
                {"key": "LUCK", "label": "??", "value": 50, "half": 25, "fifth": 10},
            ],
            "status": {"hp": 10, "san": 50, "mp": 10, "mov": 7, "armor": 0},
            "skills": [
                {"name": "??(??)", "value": 50, "half": 25, "fifth": 10},
                {"name": "??", "value": 25, "half": 12, "fifth": 5},
            ],
            "weapons": [{"name": "??", "damage": "1d3", "skill": "??(??)"}],
            "background": {}, "experiences": [], "spells": [],
            "warnings": [], "sourceFileName": "npc",
        }
        return self.add_character(room_id, keeper_id, character)

    def add_character(self, room_id: str, owner_id: str, character: dict) -> dict:
        with self._lock:
            room = self._require_room(room_id)
            owner = self._find_member(room, owner_id)
            characters = room.setdefault("characters", [])
            record = {
                **character,
                "id": uuid4().hex,
                "roomId": room_id,
                "ownerId": owner_id,
                "ownerName": owner["displayName"],
                "keeperNotes": "",
                "createdAt": self._now(),
                "updatedAt": self._now(),
            }

            existing_index = next(
                (index for index, item in enumerate(characters) if item.get("ownerId") == owner_id),
                None,
            )

            if existing_index is None:
                characters.append(record)
            else:
                record["createdAt"] = characters[existing_index].get("createdAt", record["createdAt"])
                characters[existing_index] = record

            display_name = record.get("basic", {}).get("name") or record["sourceFileName"]
            self._add_system_message(room, f"{owner['displayName']} 上传了角色卡「{display_name}」。")
            self._save()

            return deepcopy(record)

    def update_character(self, room_id: str, character_id: str, editor_id: str, updates: dict) -> dict:
        with self._lock:
            room = self._require_room(room_id)
            editor = self._find_member(room, editor_id)

            if editor["role"] != "keeper":
                raise PermissionError("Only keeper can edit character cards")

            character = self._find_character(room, character_id)

            if updates.get("basic"):
                character.setdefault("basic", {}).update(
                    {key: str(value) for key, value in updates["basic"].items() if value is not None}
                )

            if updates.get("attributes"):
                by_key = {attribute["key"]: attribute for attribute in character.get("attributes", [])}

                for item in updates["attributes"]:
                    attribute = by_key.get(item["key"])

                    if not attribute:
                        continue

                    value = item.get("value")
                    attribute["value"] = value
                    attribute["half"] = value // 2 if value is not None else None
                    attribute["fifth"] = value // 5 if value is not None else None

            if "keeperNotes" in updates:
                character["keeperNotes"] = updates.get("keeperNotes") or ""

            if "lockedFields" in updates:
                character.setdefault("lockedFields", []).clear()
                character["lockedFields"].extend(updates.get("lockedFields") or [])

            if "status" in updates and updates["status"]:
                character.setdefault("status", {}).update(
                    {k: v for k, v in updates["status"].items() if v is not None}
                )

            # Record change history
            change = {
                "editorId": editor_id,
                "editorName": editor["displayName"],
                "timestamp": self._now(),
                "changes": {k: v for k, v in updates.items() if v is not None},
            }
            character.setdefault("history", []).append(change)

            character["updatedAt"] = self._now()
            display_name = character.get("basic", {}).get("name") or character["sourceFileName"]
            self._add_system_message(room, f"{editor['displayName']} 更新了角色卡「{display_name}」。")
            self._save()

            return deepcopy(character)

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

    def _find_character(self, room: dict, character_id: str) -> dict:
        for character in room.get("characters", []):
            if character["id"] == character_id:
                return character

        raise KeyError("character_not_found")

    def _invite_code(self) -> str:
        alphabet = string.ascii_uppercase + string.digits
        existing = {room["inviteCode"] for room in self._state["rooms"].values()}

        while True:
            code = "".join(secrets.choice(alphabet) for _ in range(6))

            if code not in existing:
                return code

    def activate_room(self, room_id: str, editor_id: str) -> dict:
        with self._lock:
            room = self._require_room(room_id)
            editor = self._find_member(room, editor_id)
            if editor["role"] != "keeper":
                raise PermissionError("Only keeper can activate the room")
            if room["status"] != "preparing":
                raise ValueError("Room can only be activated from preparing status")
            room["status"] = "active"
            self._add_system_message(room, f"{editor['displayName']} ??????")
            self._save()
            return deepcopy(room)

    def end_room(self, room_id: str, editor_id: str) -> dict:
        """Mark room as ended and return summary data."""
        with self._lock:
            room = self._require_room(room_id)
            editor = self._find_member(room, editor_id)
            if editor["role"] != "keeper":
                raise PermissionError("Only keeper can end the room")
            room["status"] = "ended"
            room["endedAt"] = self._now()
            self._add_system_message(room, f"{editor['displayName']} 结束了本次跑团。")
            self._save()
            return deepcopy(room)

    def generate_summary(self, room_id: str) -> dict:
        """Generate a structured summary from room data."""
        with self._lock:
            room = self._require_room(room_id)
            messages = room.get("messages", [])
            rolls = room.get("rolls", [])
            characters = room.get("characters", [])
            voices = room.get("voices", [])

            # Extract text messages only
            text_messages = [m for m in messages if m.get("type") in ("text", "system")]

            # Build summary sections
            summary = {
                "roomName": room["name"],
                "status": room["status"],
                "startedAt": room.get("createdAt", ""),
                "endedAt": room.get("endedAt", ""),
                "memberCount": len(room.get("members", [])),
                "characters": [
                    {
                        "name": c.get("basic", {}).get("name") or c.get("sourceFileName", "??"),
                        "ownerName": c.get("ownerName", "??"),
                        "occupation": c.get("basic", {}).get("occupation", "????"),
                        "status": {
                            attr["key"]: attr["value"]
                            for attr in c.get("attributes", [])
                        },
                        "keeperNotes": c.get("keeperNotes", ""),
                    }
                    for c in characters
                ],
                "messageCount": len(text_messages),
                "rollCount": len(rolls),
                "voiceCount": len(voices),
                "keyRolls": [
                    {
                        "rollerName": r.get("rollerName", ""),
                        "expression": r.get("expression", ""),
                        "total": r.get("total"),
                        "successLabel": r.get("successLabel", ""),
                        "createdAt": r.get("createdAt", ""),
                    }
                    for r in rolls[-20:]  # last 20 rolls
                ],
                "draft": "",
            }
            return summary

    def save_summary(self, room_id: str, editor_id: str, draft: str) -> dict:
        """Save the KP-edited summary draft."""
        with self._lock:
            room = self._require_room(room_id)
            editor = self._find_member(room, editor_id)
            if editor["role"] != "keeper":
                raise PermissionError("Only keeper can edit the summary")
            summary = room.setdefault("summary", {})
            summary["draft"] = draft
            summary["updatedAt"] = self._now()
            summary["updatedBy"] = editor["displayName"]
            self._save()
            return deepcopy(summary)

        alphabet = string.ascii_uppercase + string.digits
        existing = {room["inviteCode"] for room in self._state["rooms"].values()}

        while True:
            code = "".join(secrets.choice(alphabet) for _ in range(6))

            if code not in existing:
                return code

    def get_voice_files(self, room_id: str) -> list[dict]:
        with self._lock:
            room = self._require_room(room_id)
            return deepcopy(room.get("voices", []))

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _format_roll_message(self, roll: dict) -> str:
        if roll.get("hidden"):
            return f"[暗骰] {roll['rollerName']} 进行了一次暗骰"
        label = f"「{roll['label']}」" if roll.get("label") else roll["expression"]
        if roll.get("hidden"):
            return f"[暗骰] {roll['rollerName']} {label}"
        result = f"{label} 投掷结果 {roll['total']}"

        if roll.get("successLabel"):
            result = f"{result}，{roll['successLabel']}"

        return result
