from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import secrets
import shutil
import string
from pathlib import Path
from threading import RLock
from uuid import uuid4

from app.modules.rooms.store_combat import CombatMixin
from app.modules.rooms.store_chase import ChaseMixin
from app.modules.rooms.store_npc import NpcMixin


class RoomStore(CombatMixin, ChaseMixin, NpcMixin):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data_dir = path.parent
        self._lock = RLock()
        self._state = self._load()

    def _get_db(self):
        """Return SQLite connection if initialized, else None (fallback to JSON)."""
        try:
            from app.core.db import get_db
            return get_db()
        except RuntimeError:
            return None

    def create_room(self, name: str, keeper_name: str, password: str | None = None, theme: str = "black") -> tuple[dict, str]:
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
                "roomTheme": theme,
                "messages": [],
                "rolls": [],
                "characters": [],
            }

            if password is not None and password != "":
                room["password"] = password

            self._state["rooms"][room_id] = room
            self._add_system_message(room, f"{keeper_name} 创建了房间。")
            self._save()
            return deepcopy(room), keeper_id

    def join_room(self, invite_code: str, display_name: str, password: str | None = None, role: str = "player") -> tuple[dict, str]:
        with self._lock:
            room = self._find_by_invite(invite_code)
            stored_password = room.get("password")
            if stored_password is not None and stored_password != "" and password != stored_password:
                raise PermissionError("Incorrect password")
            max_members = 50
            if len(room.get("members", [])) >= max_members:
                raise PermissionError("Room is full (max 50 members)")

            # Reuse existing offline member with same name (player reconnected)
            existing = next(
                (m for m in room.get("members", [])
                 if m["displayName"] == display_name and not m["online"]),
                None,
            )
            if existing is not None:
                existing["online"] = True
                existing["role"] = role if role in ("player", "spectator") else "player"
                # Clean up any duplicate offline members with the same name
                room["members"] = [
                    m for m in room["members"]
                    if not (m["displayName"] == display_name and not m["online"] and m["id"] != existing["id"])
                ]
                self._add_system_message(room, f"{display_name} 重新连接了房间。")
                self._save()
                return deepcopy(room), existing["id"]

            member_id = uuid4().hex
            room["members"].append(
                {
                    "id": member_id,
                    "displayName": display_name,
                    "role": role if role in ("player", "spectator") else "player",
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

    def set_room_theme(self, room_id: str, theme: str, editor_id: str) -> dict:
        with self._lock:
            room = self._require_room(room_id)
            editor = self._find_member(room, editor_id)
            if editor["role"] != "keeper":
                raise PermissionError("Only the Keeper can change room theme")
            room["roomTheme"] = theme
            self._save()
            return deepcopy(room)

    def get_room_sanitized(self, room_id: str, member_id: str) -> dict:
        """返回对指定成员过滤后的房间数据。非 KP 成员看不到暗骰和私密消息。
        未知 member_id（空字符串或不在成员列表中）视为非 KP 旁观者。
        """
        with self._lock:
            room = deepcopy(self._require_room(room_id))

        # 永远不暴露房间密码
        room.pop("password", None)

        # 查找成员；未知或空的 member_id 视为非 KP 旁观者
        is_keeper = False
        if member_id:
            member = next(
                (m for m in room.get("members", []) if m.get("id") == member_id),
                None,
            )
            if member is not None:
                is_keeper = member.get("role") == "keeper"

        if not is_keeper:
            # 完全移除暗骰消息
            room["messages"] = [
                m for m in room.get("messages", [])
                if not (m.get("type") == "dice_roll" and m.get("roll") and m["roll"].get("hidden"))
            ]

            # 完全移除暗骰记录
            room["rolls"] = [
                r for r in room.get("rolls", [])
                if not r.get("hidden")
            ]

        # 过滤聊天消息中的私密消息：非 KP 只能看到自己发送或被指定的
        room["messages"] = [
            m for m in room.get("messages", [])
            if not m.get("privateTo") or m.get("privateTo") == member_id or m.get("senderId") == member_id or is_keeper
        ]

        return room

    def add_message(self, room_id: str, sender_id: str | None, content: str, reply_to: dict | None = None, msg_type: str = "text", private_to: str | None = None, whisper_to: str | None = None, mention_ids: list[str] | None = None, attachments: list[dict] | None = None, as_character_id: str | None = None) -> dict:
        with self._lock:
            room = self._require_room(room_id)
            as_character_name: str | None = None
            sender_name: str
            sender_role: str
            if as_character_id:
                character = self._find_character(room, as_character_id)
                as_character_name = (character.get("basic", {}) or {}).get("name") or character.get("sourceFileName") or "NPC"
                # 仍以发送者本人记录 senderId / senderRole（便于权限判断与溯源），但显示名称用角色名
                sender_name = as_character_name
                if sender_id:
                    sender = next((m for m in room.get("members", []) if m["id"] == sender_id), None)
                    sender_role = sender["role"] if sender else "keeper"
                else:
                    sender_role = "keeper"
            elif sender_id:
                sender = self._find_member(room, sender_id)
                sender_name = sender["displayName"]
                sender_role = sender["role"]
            else:
                sender_name = "系统"
                sender_role = "system"
            message: dict = {
                "id": uuid4().hex,
                "type": msg_type if not private_to else "private",
                "roomId": room_id,
                "senderId": sender_id,
                "senderName": sender_name,
                "senderRole": sender_role,
                "content": content,
                "createdAt": self._now(),
            }
            if as_character_id:
                message["asCharacterId"] = as_character_id
                message["asCharacterName"] = as_character_name
            if reply_to:
                message["replyTo"] = reply_to
            if private_to:
                message["privateTo"] = private_to
            if whisper_to:
                message["whisperTo"] = whisper_to
            if mention_ids:
                message["mentionIds"] = mention_ids
            if attachments:
                message["attachments"] = attachments
            room["messages"].append(message)
            self._save()
            return deepcopy(message)

    def add_dice_roll(self, room_id: str, roller_id: str, roll: dict, as_character_id: str | None = None) -> dict:
        with self._lock:
            room = self._require_room(room_id)
            roller = self._find_member(room, roller_id)
            as_character_name: str | None = None
            roller_name = roller["displayName"]
            if as_character_id:
                character = self._find_character(room, as_character_id)
                as_character_name = (character.get("basic", {}) or {}).get("name") or character.get("sourceFileName") or "NPC"
                roller_name = as_character_name
            roll_record = {
                **roll,
                "id": uuid4().hex,
                "roomId": room_id,
                "rollerId": roller_id,
                "rollerName": roller_name,
                "rollerRole": roller["role"],
                "createdAt": self._now(),
            }
            if as_character_id:
                roll_record["asCharacterId"] = as_character_id
                roll_record["asCharacterName"] = as_character_name
            message = {
                "id": uuid4().hex,
                "type": "dice_roll",
                "roomId": room_id,
                "senderId": roller_id,
                "senderName": roller_name,
                "senderRole": roller["role"],
                "content": self._format_roll_message(roll_record),
                "roll": roll_record,
                "createdAt": roll_record["createdAt"],
            }
            if as_character_id:
                message["asCharacterId"] = as_character_id
                message["asCharacterName"] = as_character_name

            room.setdefault("rolls", []).append(roll_record)
            room["messages"].append(message)
            self._save()

            return deepcopy(roll_record)

    def character_roll(self, room_id: str, roller_id: str, character_id: str,
                       expression: str = "1d100", *, skill_name: str | None = None,
                       attribute_key: str | None = None, difficulty: str = "regular",
                       bonus_penalty: int = 0, hidden: bool = False,
                       label: str | None = None) -> dict:
        """按角色卡属性/技能值投骰。KP 可以传入任意角色卡 id（包括 NPC）；
        普通成员只能用自己绑定的角色卡。"""
        from app.modules.dice.roller import roll_dice

        with self._lock:
            room = self._require_room(room_id)
            roller = self._find_member(room, roller_id)
            character = self._find_character(room, character_id)
            if roller["role"] != "keeper":
                if character.get("ownerId") != roller_id:
                    raise PermissionError("You can only roll with your own character card")

            target_value: int | None = None
            resolved_label: str = label or ""
            if skill_name:
                for sk in character.get("skills", []):
                    if sk.get("name") == skill_name:
                        val = sk.get("value") or 50
                        target_value = val if difficulty == "regular" else (val // 2 if difficulty == "hard" else val // 5)
                        resolved_label = f"{character.get('basic', {}).get('name', '??')} | {skill_name}"
                        break
            if target_value is None and attribute_key:
                for attr in character.get("attributes", []):
                    if attr.get("key") == attribute_key:
                        val = attr.get("value") or 50
                        target_value = val if difficulty == "regular" else (val // 2 if difficulty == "hard" else val // 5)
                        resolved_label = f"{character.get('basic', {}).get('name', '??')} | {attr.get('label', attribute_key)}"
                        break
            if target_value is None and not label:
                resolved_label = f"{character.get('basic', {}).get('name', '??')}"

            roll = roll_dice(expression, target_value=target_value,
                             bonus_penalty=bonus_penalty,
                             label=resolved_label, hidden=hidden)
            return self.add_dice_roll(room_id, roller_id, roll, as_character_id=character_id)

    def add_character(self, room_id: str, owner_id: str, character: dict, replace_existing: bool = True) -> dict:
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
            ) if replace_existing else None

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
                init = character.get("initialStatus") or {}
                capped: dict[str, object] = {}
                for k, v in updates["status"].items():
                    if v is None:
                        continue
                    # Cap HP/SAN/MP at their max values (initialStatus is immutable)
                    if k in ("hp", "san", "mp") and k in init and init[k] is not None:
                        v = min(v, init[k])
                    capped[k] = v
                character.setdefault("status", {}).update(capped)

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

    def remove_character(self, room_id: str, owner_id: str) -> dict:
        with self._lock:
            room = self._require_room(room_id)
            characters = room.get("characters", [])
            idx = next((i for i, c in enumerate(characters) if c.get("ownerId") == owner_id), None)
            if idx is not None:
                removed = characters.pop(idx)
                owner = self._find_member(room, owner_id)
                display_name = removed.get("basic", {}).get("name") or removed.get("sourceFileName", "?")
                self._add_system_message(room, f"{owner['displayName']} 的角色卡「{display_name}」已移除。")
                self._save()
            return deepcopy(room)

    def delete_character(self, room_id: str, character_id: str, editor_id: str) -> dict:
        """Delete a specific character by ID. Only KP can delete NPC cards."""
        with self._lock:
            room = self._require_room(room_id)
            editor = self._find_member(room, editor_id)
            if editor["role"] != "keeper":
                raise PermissionError("Only keeper can delete characters")
            characters = room.get("characters", [])
            idx = next((i for i, c in enumerate(characters) if c.get("id") == character_id), None)
            if idx is None:
                raise KeyError("character_not_found")
            removed = characters.pop(idx)
            display_name = removed.get("basic", {}).get("name") or removed.get("sourceFileName", "?")
            self._add_system_message(room, f"{editor['displayName']} 删除了角色卡「{display_name}」。")
            self._save()
            return deepcopy(room)

    def delete_room(self, room_id: str) -> bool:
        with self._lock:
            if room_id in self._state["rooms"]:
                del self._state["rooms"][room_id]
                self._save()
                return True
            return False

    def delete_message(self, room_id: str, message_id: str, editor_id: str) -> dict | None:
        """Delete a message. KP can delete any message; sender can delete own message."""
        with self._lock:
            room = self._require_room(room_id)
            editor = self._find_member(room, editor_id)
            messages = room.get("messages", [])
            idx = next((i for i, m in enumerate(messages) if m.get("id") == message_id), None)
            if idx is None:
                raise KeyError("message_not_found")
            msg = messages[idx]
            is_keeper = editor["role"] == "keeper"
            is_own = msg.get("senderId") == editor_id
            if not is_keeper and not is_own:
                raise PermissionError("Only the Keeper or message sender can delete a message")
            removed = messages.pop(idx)
            self._add_system_message(room, f"{editor['displayName']} 删除了一条消息。")
            self._save()
            return removed

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
        db = self._get_db()
        if db is not None:
            return self._load_from_sqlite(db)
        return self._load_from_json()

    def _load_from_sqlite(self, db) -> dict:
        state: dict = {"rooms": {}}

        room_rows = db.execute("SELECT * FROM rooms").fetchall()
        for rr in room_rows:
            room_id = rr["id"]
            room = {
                "id": room_id,
                "name": rr["name"],
                "status": rr["status"],
                "inviteCode": rr["invite_code"],
                "password": rr["password"],
                "roomTheme": rr["room_theme"] or "black",
                "moduleIntro": rr["module_intro"],
                "summary": json.loads(rr["summary"]) if rr["summary"] else None,
                "createdAt": rr["created_at"],
                "endedAt": rr["ended_at"],
                "members": [],
                "messages": [],
                "rolls": [],
                "characters": [],
                "voices": [],
            }

            # Members
            mem_rows = db.execute(
                "SELECT * FROM room_members WHERE room_id = ?", (room_id,)
            ).fetchall()
            for mr in mem_rows:
                room["members"].append({
                    "id": mr["id"],
                    "displayName": mr["display_name"],
                    "role": mr["role"],
                    "joinedAt": mr["joined_at"],
                    "online": bool(mr["online"]),
                    "userId": mr["user_id"],
                })

            # Messages
            msg_rows = db.execute(
                "SELECT * FROM messages WHERE room_id = ? ORDER BY created_at", (room_id,)
            ).fetchall()
            for mr in msg_rows:
                msg = {
                    "id": mr["id"],
                    "type": mr["type"],
                    "roomId": room_id,
                    "senderId": mr["sender_id"],
                    "senderName": mr["sender_name"],
                    "senderRole": mr["sender_role"],
                    "content": mr["content"],
                    "createdAt": mr["created_at"],
                }
                if mr["data_json"]:
                    extra = json.loads(mr["data_json"])
                    msg.update(extra)
                if msg["type"] == "dice_roll" and "roll" in msg:
                    room["rolls"].append(msg["roll"])
                room["messages"].append(msg)

            # Characters
            char_rows = db.execute(
                "SELECT * FROM characters WHERE room_id = ?", (room_id,)
            ).fetchall()
            for cr in char_rows:
                char = json.loads(cr["data_json"])
                char["id"] = cr["id"]
                char["roomId"] = room_id
                char["ownerId"] = cr["owner_id"]
                char["ownerName"] = cr["owner_name"]
                char["createdAt"] = cr["created_at"]
                char["updatedAt"] = cr["updated_at"]
                room["characters"].append(char)

            # Dice rolls (separate from messages - standalone roll records)
            roll_rows = db.execute(
                "SELECT * FROM dice_rolls WHERE room_id = ? ORDER BY created_at", (room_id,)
            ).fetchall()
            for dr in roll_rows:
                roll = json.loads(dr["data_json"])
                roll["id"] = dr["id"]
                roll["roomId"] = room_id
                roll["rollerId"] = dr["roller_id"]
                roll["createdAt"] = dr["created_at"]
                # Avoid duplicates: rolls might already be in messages
                existing_ids = {r["id"] for r in room["rolls"]}
                if roll["id"] not in existing_ids:
                    room["rolls"].append(roll)

            state["rooms"][room_id] = room

        return state

    def _load_from_json(self) -> dict:
        if not self.path.exists():
            return {"rooms": {}}
        try:
            with self.path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except json.JSONDecodeError:
            return {"rooms": {}}

    def _save(self) -> None:
        db = self._get_db()
        if db is not None:
            self._save_to_sqlite(db)
        else:
            self._save_to_json()

    def _save_room_to_sqlite(self, db, room: dict) -> None:
        room_id = room["id"]
        # Upsert room row
        db.execute(
            """INSERT OR REPLACE INTO rooms
               (id, name, status, invite_code, password, room_theme,
                module_intro, summary, created_at, ended_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                room_id,
                room.get("name", ""),
                room.get("status", "preparing"),
                room.get("inviteCode", ""),
                room.get("password"),
                room.get("roomTheme", "black"),
                room.get("moduleIntro"),
                json.dumps(room.get("summary"), ensure_ascii=False) if room.get("summary") else None,
                room.get("createdAt", self._now()),
                room.get("endedAt"),
            ),
        )

        # Members: delete and re-insert
        db.execute("DELETE FROM room_members WHERE room_id = ?", (room_id,))
        for m in room.get("members", []):
            db.execute(
                """INSERT INTO room_members (id, room_id, user_id, display_name, role, online, joined_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    m["id"], room_id,
                    m.get("userId"),
                    m["displayName"], m["role"],
                    int(m.get("online", False)),
                    m.get("joinedAt", self._now()),
                ),
            )

        # Messages: delete and re-insert
        db.execute("DELETE FROM messages WHERE room_id = ?", (room_id,))
        for msg in room.get("messages", []):
            extra = {}
            for key in ("roll", "replyTo", "attachment", "attachments", "privateTo", "whisperTo", "mentionIds"):
                if msg.get(key):
                    extra[key] = msg[key]
            db.execute(
                """INSERT INTO messages (id, room_id, type, sender_id, sender_name, sender_role, content, data_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    msg["id"], room_id,
                    msg.get("type", "text"),
                    msg.get("senderId"),
                    msg.get("senderName", ""),
                    msg.get("senderRole", "player"),
                    msg.get("content", ""),
                    json.dumps(extra, ensure_ascii=False) if extra else None,
                    msg.get("createdAt", self._now()),
                ),
            )

        # Characters: delete and re-insert
        db.execute("DELETE FROM characters WHERE room_id = ?", (room_id,))
        for char in room.get("characters", []):
            char_data = {k: v for k, v in char.items()
                         if k not in ("id", "roomId", "ownerId", "ownerName", "createdAt", "updatedAt")}
            db.execute(
                """INSERT INTO characters (id, room_id, owner_id, owner_name, data_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    char.get("id", ""), room_id,
                    char.get("ownerId"),
                    char.get("ownerName", ""),
                    json.dumps(char_data, ensure_ascii=False),
                    char.get("createdAt", self._now()),
                    char.get("updatedAt", self._now()),
                ),
            )

        # Dice rolls: delete and re-insert
        db.execute("DELETE FROM dice_rolls WHERE room_id = ?", (room_id,))
        for roll in room.get("rolls", []):
            roll_data = {k: v for k, v in roll.items()
                         if k not in ("id", "roomId", "rollerId", "createdAt")}
            db.execute(
                """INSERT INTO dice_rolls (id, room_id, roller_id, data_json, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    roll.get("id", ""), room_id,
                    roll.get("rollerId", ""),
                    json.dumps(roll_data, ensure_ascii=False),
                    roll.get("createdAt", self._now()),
                ),
            )

    def _save_to_sqlite(self, db) -> None:
        with db:  # transaction
            for room in self._state.get("rooms", {}).values():
                self._save_room_to_sqlite(db, room)

    def _save_to_json(self) -> None:
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
            self._add_system_message(room, f"{editor['displayName']} 激活了房间，游戏开始！")
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
                        "name": c.get("basic", {}).get("name") or c.get("sourceFileName", "未知"),
                        "ownerName": c.get("ownerName", "未知"),
                        "occupation": c.get("basic", {}).get("occupation", "未知职业"),
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

    # ── Module Intro ──

    def update_module_intro(self, room_id: str, editor_id: str, intro: str) -> dict:
        with self._lock:
            room = self._require_room(room_id)
            editor = self._find_member(room, editor_id)
            if editor["role"] != "keeper":
                raise PermissionError("Only keeper can edit module intro")
            room["moduleIntro"] = intro
            self._add_system_message(room, f"{editor['displayName']} 更新了模组简介。")
            self._save()
            return deepcopy(room)

    # ── SAN Check ──

    def san_check_roll(self, room_id: str, roller_id: str, character_id: str,
                       success_loss: str, failure_loss: str, hidden: bool) -> dict:
        from app.modules.dice.roller import roll_dice, insanity_check
        with self._lock:
            room = self._require_room(room_id)
            roller = self._find_member(room, roller_id)
            character = self._find_character(room, character_id)

            status = character.get("status") or {}
            init_status = character.get("initialStatus") or {}
            current_san = status.get("san") if status.get("san") is not None else (
                init_status.get("san") if init_status.get("san") is not None else 0
            )
            max_san = init_status.get("san") if init_status.get("san") is not None else 99

            # Roll 1d100 vs current SAN
            dice_result = roll_dice("1d100", target_value=current_san, bonus_penalty=0)
            success_level = dice_result.get("successLevel")
            is_success = success_level in ("critical", "extreme", "hard", "regular")

            # Parse loss expression and roll the loss dice
            loss_expr = success_loss if is_success else failure_loss
            loss_amount, loss_dice = self._parse_loss(loss_expr)

            # If the loss was a dice roll (not plain number), record it as a visible roll
            loss_record = None
            if loss_dice is not None:
                name = character.get("basic", {}).get("name", "未知")
                loss_dice["label"] = f"{name} SAN损失 ({'成功' if is_success else '失败'}→{loss_expr})"
                loss_dice["hidden"] = hidden
                loss_record = self.add_dice_roll(room_id, roller_id, loss_dice)

            # Update character SAN (capped between 0 and max_san)
            new_san = max(0, min(max_san, current_san - loss_amount))
            character.setdefault("status", {})["san"] = new_san

            # Full insanity check (COC 7e CRB p155-164)
            # Track daily cumulative loss per character
            daily_key = f"san_daily_{character_id}"
            cumulative = (room.get(daily_key, 0) or 0) + loss_amount
            room[daily_key] = cumulative
            int_value = 50
            for attr in character.get("attributes", []):
                if attr.get("key") == "INT":
                    int_value = attr.get("value") or 50
                    break
            insanity = insanity_check(loss_amount, new_san, max_san, cumulative, int_value, pre_loss_san=current_san)

            # Record the 1d100 SAN check result
            label = f"{character.get('basic', {}).get('name', '未知')} SAN CHECK (当前SAN={current_san})"
            dice_result["label"] = label
            dice_result["hidden"] = hidden

            roll_record = self.add_dice_roll(room_id, roller_id, dice_result)

            # Build SAN check result info
            result = {
                **roll_record,
                "characterId": character_id,
                "characterName": character.get("basic", {}).get("name", ""),
                "currentSan": current_san,
                "newSan": new_san,
                "sanLost": loss_amount,
                "lossParams": f"{success_loss}/{failure_loss}",
                "lossExprRolled": loss_expr,
                "isSuccess": is_success,
                "insanity": insanity,
            }
            if loss_record:
                result["lossRecord"] = loss_record

            # System message for SAN change — show the loss dice breakdown if available
            loss_detail = f"{loss_expr}=[{', '.join(str(r) for r in loss_dice['breakdown'][0]['rolls'])}]" if loss_dice else loss_expr
            loss_str = f"-{loss_amount}" if loss_amount > 0 else "0"
            msg = (f"{character.get('basic', {}).get('name', '未知')} SAN CHECK "
                f"{'成功' if is_success else '失败'}（{success_loss}/{failure_loss}），"
                f"实际损失：{loss_detail} → {loss_str}，"
                f"SAN {current_san} → {new_san}")
            if insanity.get("permanentInsanity"):
                msg += " [永久疯狂！调查员退场]"
            elif insanity.get("needsIntRoll"):
                msg += " [需 INT 检定判定临时疯狂]"
            if insanity.get("indefiniteInsanity"):
                msg += " [单日累计触发不定期疯狂]"
            self._add_system_message(room, msg)

            self._save()
            return result

    def _parse_loss(self, expr: str) -> tuple[int, dict | None]:
        """Parse a SAN loss expression like '1', '1D6', '1D4+1' and return (amount, dice_result).

        dice_result is None for plain numbers; otherwise it's the full roll_dice dict
        so callers can record it as a visible dice roll.
        """
        import re
        from app.modules.dice.roller import roll_dice
        expr = expr.strip().upper()
        if re.match(r'^\d+$', expr):
            return int(expr), None
        result = roll_dice(expr)
        return result["total"], result
    def start_combat(self, room_id: str, editor_id: str) -> dict:
        with self._lock:
            room = self._require_room(room_id)
            editor = self._find_member(room, editor_id)
            if editor["role"] != "keeper":
                raise PermissionError("Only keeper can start combat")

            actors = []
            for member in room["members"]:
                if member["role"] == "spectator":
                    continue
                char = next((c for c in room.get("characters", [])
                           if c.get("ownerId") == member["id"] and c.get("active") is not False), None)
                if not char:
                    continue
                attrs = {a["key"]: (a["value"] or 50) for a in char.get("attributes", [])}
                dex = attrs.get("DEX", 50)
                db, build = self._compute_db(attrs.get("STR", 50), attrs.get("SIZ", 50))
                status = char.get("status") or {}
                actors.append({
                    "memberId": member["id"],
                    "characterId": char["id"],
                    "displayName": char.get("basic", {}).get("name") or member["displayName"],
                    "dex": dex,
                    "hp": status.get("hp") or 0,
                    "hpMax": (char.get("initialStatus") or {}).get("hp") or status.get("hp") or 10,
                    "db": db,
                    "build": build,
                    "hasActedThisRound": False,
                })

            actors.sort(key=lambda a: a["dex"], reverse=True)

            combat_state = {
                "active": True,
                "roundNumber": 1,
                "actors": actors,
                "currentActorIndex": 0,
                "createdAt": self._now(),
            }
            room["combatState"] = combat_state
            self._add_system_message(room, f"{editor['displayName']} 开始了战斗轮次！Round 1")
            self._save()
            return deepcopy(combat_state)
    def act_combat(self, room_id: str, attacker_id: str, weapon_index: int,
                   defender_id: str, action_type: str, hidden: bool) -> dict:
        from app.modules.dice.roller import roll_dice, opposed_check
        with self._lock:
            room = self._require_room(room_id)
            cs = room.get("combatState")
            if not cs or not cs.get("active"):
                raise ValueError("No active combat round")

            actors = cs["actors"]
            current_idx = cs["currentActorIndex"]
            if current_idx >= len(actors):
                raise ValueError("Combat round already ended")

            current_actor = actors[current_idx]
            if current_actor["memberId"] != attacker_id:
                raise ValueError("Not your turn")
            if current_actor["hasActedThisRound"]:
                raise ValueError("This actor has already acted this round")

            attacker_char = self._find_character(room, current_actor["characterId"])
            defender_actor = next((a for a in actors if a["memberId"] == defender_id), None)
            if not defender_actor:
                raise ValueError("Target not found in combat")
            defender_char = self._find_character(room, defender_actor["characterId"])

            # Get weapon info
            weapons = attacker_char.get("weapons", [])
            weapon = weapons[weapon_index] if 0 <= weapon_index < len(weapons) else None
            weapon_name = weapon.get("name", "徒手") if weapon else "徒手"
            weapon_damage = str(weapon.get("damage", "1D3")) if weapon else "1D3"
            weapon_skill_name = str(weapon.get("skill", "格斗(斗殴)")) if weapon else "格斗(斗殴)"
            is_impaling = self._is_impaling_weapon(weapon)

            # Find attacker's skill value for this weapon
            attacker_skills = attacker_char.get("skills", [])
            skill_value = 50  # default
            for sk in attacker_skills:
                if sk.get("name") == weapon_skill_name:
                    skill_value = sk.get("value") or 50
                    break

            # Roll attacker's attack
            attack_roll = roll_dice("1d100", target_value=skill_value, bonus_penalty=0)

            # Defender action
            if action_type == "dodge":
                defender_skills = defender_char.get("skills", [])
                dodge_value = 25
                for sk in defender_skills:
                    if sk.get("name") == "闪避":
                        dodge_value = sk.get("value") or 25
                        break
                defend_roll = roll_dice("1d100", target_value=dodge_value, bonus_penalty=0)
                # Opposed: attack vs dodge (defender wins ties per CRB p108)
                winner = opposed_check(attack_roll["total"], skill_value,
                                      defend_roll["total"], dodge_value,
                                      defender_wins_tie=True)
                attacker_wins = winner.get("winner") == "actor"
                if attacker_wins:
                    # Apply damage (defender attempted dodge, failed — CRB p108)
                    damage = self._calc_damage(weapon_damage, current_actor["db"],
                                              attack_roll.get("successLevel"),
                                              is_impaling=is_impaling,
                                              is_fighting_back=False)
                    new_hp = max(0, defender_actor["hp"] - damage)
                    defender_actor["hp"] = new_hp
                    defender_char.setdefault("status", {})["hp"] = new_hp
                    self._add_system_message(room,
                        f"⚔️ [闪避失败] {current_actor['displayName']} 用{weapon_name}攻击"
                        f"{defender_actor['displayName']}（{defend_roll['total']}/{dodge_value} 闪避检定未通过），"
                        f"造成 {damage} 点伤害！HP → {defender_actor['hp']}")
                    # Check major wound
                    if damage >= defender_actor["hpMax"] // 2:
                        self._add_system_message(room,
                            f"💀 {defender_actor['displayName']} 受到重伤！")
                else:
                    self._add_system_message(room,
                        f"💨 [闪避成功] {defender_actor['displayName']} 闪避了 {current_actor['displayName']} "
                        f"用{weapon_name}的攻击（{defend_roll['total']}/{dodge_value}）")
            elif action_type == "fight_back":
                # Fight back — contested fighting roll, attacker wins ties (CRB p108)
                defender_skills = defender_char.get("skills", [])
                fight_value = 25
                defender_weapon = None
                defender_weapon_damage = "1D3"
                def_weapons = defender_char.get("weapons", [])
                if def_weapons:
                    defender_weapon = def_weapons[0]
                    defender_weapon_damage = str(defender_weapon.get("damage", "1D3"))
                for sk in defender_skills:
                    if sk.get("name") in ("格斗(斗殴)", "格斗", "斗殴"):
                        fight_value = sk.get("value") or 25
                        break
                defend_roll = roll_dice("1d100", target_value=fight_value, bonus_penalty=0)
                winner = opposed_check(attack_roll["total"], skill_value,
                                      defend_roll["total"], fight_value,
                                      defender_wins_tie=False)
                attacker_wins = winner.get("winner") == "actor"
                if attacker_wins:
                    damage = self._calc_damage(weapon_damage, current_actor["db"],
                                              attack_roll.get("successLevel"),
                                              is_impaling=is_impaling,
                                              is_fighting_back=True)
                    new_hp = max(0, defender_actor["hp"] - damage)
                    defender_actor["hp"] = new_hp
                    defender_char.setdefault("status", {})["hp"] = new_hp
                    self._add_system_message(room,
                        f"⚔️ [反击失败] {current_actor['displayName']} 用{weapon_name}攻击"
                        f"{defender_actor['displayName']}（反击检定未通过），造成 {damage} 点伤害！HP → {new_hp}")
                    if damage >= defender_actor["hpMax"] // 2:
                        self._add_system_message(room,
                            f"💀 {defender_actor['displayName']} 受到重伤！")
                else:
                    # Defender won fight-back — apply defender's damage to attacker (CRB p108)
                    def_is_impaling = self._is_impaling_weapon(defender_weapon)
                    counter_damage = self._calc_damage(defender_weapon_damage, defender_actor.get("db", "0"),
                                                       defend_roll.get("successLevel"),
                                                       is_impaling=def_is_impaling,
                                                       is_fighting_back=True)
                    new_hp = max(0, current_actor["hp"] - counter_damage)
                    current_actor["hp"] = new_hp
                    attacker_char.setdefault("status", {})["hp"] = new_hp
                    def_wname = (defender_weapon.get("name") if defender_weapon else "徒手") or "徒手"
                    self._add_system_message(room,
                        f"🛡️ [反击成功] {defender_actor['displayName']} 反击 {current_actor['displayName']}，"
                        f"用{def_wname}造成 {counter_damage} 点伤害！HP → {new_hp}")
                    if counter_damage >= current_actor["hpMax"] // 2:
                        self._add_system_message(room,
                            f"💀 {current_actor['displayName']} 受到重伤！")
            elif action_type == "attack":
                # Direct attack — no defender action roll, hit on success (CRB p102-104)
                atk_success = attack_roll.get("successLevel") in ("critical", "extreme", "hard", "regular")
                if atk_success:
                    damage = self._calc_damage(weapon_damage, current_actor["db"],
                                              attack_roll.get("successLevel"),
                                              is_impaling=is_impaling,
                                              is_fighting_back=False)
                    new_hp = max(0, defender_actor["hp"] - damage)
                    defender_actor["hp"] = new_hp
                    defender_char.setdefault("status", {})["hp"] = new_hp
                    self._add_system_message(room,
                        f"⚔️ [直接攻击] {current_actor['displayName']} 用{weapon_name}"
                        f"命中 {defender_actor['displayName']}，造成 {damage} 点伤害！HP → {new_hp}")
                    if damage >= defender_actor["hpMax"] // 2:
                        self._add_system_message(room,
                            f"💀 {defender_actor['displayName']} 受到重伤！")
                else:
                    self._add_system_message(room,
                        f"❌ [直接攻击] {current_actor['displayName']} 用{weapon_name}攻击"
                        f"{defender_actor['displayName']}，未命中（{attack_roll['total']}/{skill_value}）")
            else:
                # Maneuver — contested check without damage (CRB p90-92)
                defender_skills = defender_char.get("skills", [])
                # Use appropriate skill for maneuver; default to STR-based resistance
                resist_value = 25
                for attr in defender_char.get("attributes", []):
                    if attr.get("key") == "STR":
                        resist_value = attr.get("value") or 25
                        break
                defend_roll = roll_dice("1d100", target_value=resist_value, bonus_penalty=0)
                winner = opposed_check(attack_roll["total"], skill_value,
                                      defend_roll["total"], resist_value,
                                      defender_wins_tie=False)
                attacker_wins = winner.get("winner") == "actor"
                if attacker_wins:
                    self._add_system_message(room,
                        f"🤼 [战术动作] {current_actor['displayName']} 对 {defender_actor['displayName']} "
                        f"的战术动作成功！（{attack_roll['total']}/{skill_value} vs {defend_roll['total']}/{resist_value}）")
                else:
                    self._add_system_message(room,
                        f"🤼 [战术动作] {defender_actor['displayName']} 抵抗了 {current_actor['displayName']} "
                        f"的战术动作（{defend_roll['total']}/{resist_value} vs {attack_roll['total']}/{skill_value}）")

            # Mark current actor as acted
            current_actor["hasActedThisRound"] = True

            # Record the dice roll
            atk_sl = attack_roll.get("successLevel")
            roll_record = {
                "expression": "1d100",
                "total": attack_roll["total"],
                "breakdown": attack_roll.get("breakdown", []),
                "targetValue": skill_value,
                "bonusPenalty": 0,
                "successLevel": atk_sl,
                "successLabel": attack_roll.get("successLabel"),
                "isSuccess": atk_sl in ("critical", "extreme", "hard", "regular"),
                "hidden": hidden,
                "label": f"⚔️ {current_actor['displayName']} {weapon_name} → {defender_actor['displayName']}",
            }
            self.add_dice_roll(room_id, attacker_id, roll_record)

            # Advance initiative
            cs["currentActorIndex"] += 1
            if cs["currentActorIndex"] >= len(actors):
                # Next round
                cs["roundNumber"] += 1
                cs["currentActorIndex"] = 0
                for a in actors:
                    a["hasActedThisRound"] = False
                self._add_system_message(room, f"🔄 Round {cs['roundNumber']} 开始！")

            self._save()
            return deepcopy(cs)
    def _calc_damage(self, weapon_damage: str, db: str, success_level: str | None,
                     is_impaling: bool = False, is_fighting_back: bool = False) -> int:
        """COC 7e 伤害计算 (CRB p104-108).

        - 极难/大成功：最大武器伤害 + 最大 DB（不掷骰）
        - 穿刺武器且非反击时：额外 + 武器伤害掷骰（穿刺规则 CRB p104）
        - 反击成功时：只取最大伤害，不加穿刺骰（CRB p108）
        """
        from app.modules.dice.roller import roll_dice
        # Normalize DB expression: _compute_db returns "+1D4" etc., but roll_dice expects "1D4"
        db_expr = db.lstrip("+") if db else db
        wd = roll_dice(weapon_damage)["total"]
        db_val = roll_dice(db_expr)["total"] if db_expr and db_expr not in ("0", "-1", "-2") else (
            int(db_expr) if db_expr and db_expr.lstrip('-').isdigit() else 0)
        if success_level in ("extreme", "critical"):
            max_wd = self._max_damage(weapon_damage)
            max_db_val = self._max_damage(db_expr) if db_expr and db_expr not in ("0", "-1", "-2") else 0
            if is_impaling and not is_fighting_back:
                return max_wd + max_db_val + wd  # impale: max + weapon damage roll
            return max_wd + max_db_val  # max damage only
        return max(0, wd + db_val)
    def end_combat(self, room_id: str, editor_id: str) -> dict:
        with self._lock:
            room = self._require_room(room_id)
            editor = self._find_member(room, editor_id)
            if editor["role"] != "keeper":
                raise PermissionError("Only keeper can end combat")
            if "combatState" in room:
                del room["combatState"]
            self._add_system_message(room, f"{editor['displayName']} 结束了战斗轮次。")
            self._save()
            return deepcopy(room)
    def get_chase_state(self, room_id: str) -> dict | None:
        with self._lock:
            room = self._require_room(room_id)
            cs = room.get("chaseState")
            return deepcopy(cs) if cs else None
    def end_chase(self, room_id: str, editor_id: str) -> dict:
        with self._lock:
            room = self._require_room(room_id)
            editor = self._find_member(room, editor_id)
            if editor["role"] != "keeper":
                raise PermissionError("Only keeper can end chase")
            if "chaseState" in room:
                del room["chaseState"]
            self._add_system_message(room, f"{editor['displayName']} 结束了追逐轮次。")
            self._save()
            return deepcopy(room)

    def add_voice_message(self, room_id: str, sender_id: str, voice_record: dict) -> dict:
        """添加语音消息到房间。同时添加到 messages 列表和 voices 列表。"""
        with self._lock:
            room = self._require_room(room_id)
            sender = self._find_member(room, sender_id)
            voice_record["senderName"] = sender["displayName"]
            room.setdefault("voices", []).append(voice_record)

            message = {
                "id": uuid4().hex,
                "type": "voice",
                "senderId": sender_id,
                "senderName": sender["displayName"],
                "content": "[语音消息]",
                "voiceId": voice_record["id"],
                "voiceUrl": voice_record["url"],
                "voiceDuration": voice_record.get("duration", 0),
                "createdAt": self._now(),
            }
            room.setdefault("messages", []).append(message)
            self._save()
            return deepcopy(message)

    def get_voice_files(self, room_id: str) -> list[dict]:
        with self._lock:
            room = self._require_room(room_id)
            return deepcopy(room.get("voices", []))

    def get_rooms_by_user(self, user_id: str) -> list[dict]:
        """Return rooms where the given user is a member. Query from SQLite if available, else scan memory."""
        db = self._get_db()
        if db is not None:
            rows = db.execute(
                "SELECT DISTINCT room_id FROM room_members WHERE user_id = ?", (user_id,)
            ).fetchall()
            with self._lock:
                return [
                    {"id": r["room_id"], "name": self._state["rooms"].get(r["room_id"], {}).get("name", ""),
                     "status": self._state["rooms"].get(r["room_id"], {}).get("status", ""),
                     "createdAt": self._state["rooms"].get(r["room_id"], {}).get("createdAt", ""),
                     "inviteCode": self._state["rooms"].get(r["room_id"], {}).get("inviteCode", "")}
                    for r in rows if r["room_id"] in self._state["rooms"]
                ]
        with self._lock:
            result = []
            for room in self._state.get("rooms", {}).values():
                for m in room.get("members", []):
                    if m.get("userId") == user_id:
                        result.append({
                            "id": room["id"], "name": room.get("name", ""),
                            "status": room.get("status", ""),
                            "createdAt": room.get("createdAt", ""),
                            "inviteCode": room.get("inviteCode", ""),
                        })
                        break
            return result

    def bind_member_to_user(self, room_id: str, member_id: str, user_id: str) -> dict:
        """Link a guest member to a registered user account."""
        with self._lock:
            room = self._require_room(room_id)
            member = self._find_member(room, member_id)
            member["userId"] = user_id
            self._save()
            return deepcopy(room)

    def cleanup_empty_rooms(self, max_idle_seconds: int = 30) -> int:
        """Remove only truly abandoned 'preparing' rooms with no meaningful content.

        Active and ended rooms are never auto-deleted — their data is persistent.
        Only 'preparing' rooms that have been idle with no online members and
        contain at most 1 system message (the creation notice) are cleaned up.
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            to_remove = []
            for room_id, room in self._state.get("rooms", {}).items():
                # Never clean up active or ended rooms
                status = room.get("status", "preparing")
                if status != "preparing":
                    continue

                has_online = any(m.get("online") for m in room.get("members", []))
                if has_online:
                    continue

                # Only clean up rooms with no real content (≤1 system message)
                messages = room.get("messages", [])
                if len(messages) > 1:
                    continue
                has_characters = len(room.get("characters", [])) > 0
                has_rolls = len(room.get("rolls", [])) > 0
                if has_characters or has_rolls:
                    continue

                # Check idle time based on creation time
                latest_ts = room.get("createdAt", "")
                if not latest_ts:
                    continue
                try:
                    latest_dt = datetime.fromisoformat(latest_ts)
                    idle_seconds = (now - latest_dt).total_seconds()
                except (ValueError, TypeError):
                    continue
                if idle_seconds > max_idle_seconds:
                    to_remove.append(room_id)

            for rid in to_remove:
                del self._state["rooms"][rid]
                upload_dir = self.data_dir / "uploads" / rid
                if upload_dir.exists():
                    try:
                        shutil.rmtree(upload_dir)
                    except OSError:
                        pass
            if to_remove:
                self._save()
                db = self._get_db()
                if db is not None:
                    for rid in to_remove:
                        db.execute("DELETE FROM rooms WHERE id = ?", (rid,))
                        db.execute("DELETE FROM room_members WHERE room_id = ?", (rid,))
                        db.execute("DELETE FROM messages WHERE room_id = ?", (rid,))
                        db.execute("DELETE FROM characters WHERE room_id = ?", (rid,))
                        db.execute("DELETE FROM dice_rolls WHERE room_id = ?", (rid,))
                    db.commit()
            return len(to_remove)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _format_roll_message(self, roll: dict) -> str:
        if roll.get("hidden"):
            return f"[暗骰] {roll['rollerName']} 进行了一次暗骰"
        label = f"「{roll['label']}」" if roll.get("label") else roll["expression"]
        result = f"{label} 投掷结果 {roll['total']}"
        if roll.get("successLabel"):
            result = f"{result}，{roll['successLabel']}"
        return result