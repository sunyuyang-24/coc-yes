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


class RoomStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data_dir = path.parent
        self._lock = RLock()
        self._state = self._load()

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
        """返回对指定成员过滤后的房间数据。非 KP 成员看不到暗骰和私密消息。"""
        with self._lock:
            room = deepcopy(self._require_room(room_id))
        member = self._find_member(room, member_id)
        is_keeper = member["role"] == "keeper"

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

        # 过滤聊天消息中的私密消息
        room["messages"] = [
            m for m in room.get("messages", [])
            if not m.get("privateTo") or m.get("privateTo") == member_id or m.get("senderId") == member_id or is_keeper
        ]

        return room

    def add_message(self, room_id: str, sender_id: str | None, content: str, reply_to: dict | None = None, msg_type: str = "text", private_to: str | None = None, whisper_to: str | None = None, mention_ids: list[str] | None = None, attachment: dict | None = None) -> dict:
        with self._lock:
            room = self._require_room(room_id)
            if sender_id:
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
            if reply_to:
                message["replyTo"] = reply_to
            if private_to:
                message["privateTo"] = private_to
            if whisper_to:
                message["whisperTo"] = whisper_to
            if mention_ids:
                message["mentionIds"] = mention_ids
            if attachment:
                message["attachment"] = attachment
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
        label_map = {
            "STR": "力量", "DEX": "敏捷", "POW": "意志",
            "CON": "体质", "APP": "外貌", "EDU": "教育",
            "SIZ": "体型", "INT": "智力", "LUCK": "幸运",
        }
        character = {
            "basic": {"name": f"{name} (NPC)", "occupation": "NPC"},
            "attributes": [
                {"key": k, "label": v, "value": 50, "half": 25, "fifth": 10}
                for k, v in label_map.items()
            ],
            "status": {"hp": 10, "san": 50, "mp": 10, "mov": 7, "armor": 0},
            "initialStatus": {"hp": 10, "san": 50, "mp": 10, "mov": 7, "armor": 0},
            "skills": [
                {"name": "闪避", "value": 25, "half": 12, "fifth": 5},
            ],
            "weapons": [{"name": "拳头", "damage": "1d3", "skill": "拳头/摔跌"}],
            "background": {}, "experiences": [], "spells": [],
            "warnings": [], "sourceFileName": "npc",
            "isNpc": True,
        }
        return self.add_character(room_id, keeper_id, character, replace_existing=False)

    def create_npc_from_text(self, room_id: str, keeper_id: str, npc_text: str) -> dict:
        """Parse free-form NPC text and create a character card."""
        import re

        label_map = {
            "STR": "力量", "DEX": "敏捷", "POW": "意志",
            "CON": "体质", "APP": "外貌", "EDU": "教育",
            "SIZ": "体型", "INT": "智力", "LUCK": "幸运",
        }

        # Default values
        attrs: dict[str, int] = {k: 50 for k in label_map}
        name = "NPC"
        occupation = "NPC"
        skills: list[dict] = []
        weapons: list[dict] = []
        background_parts: list[str] = []
        hp_override: int | None = None
        san_override: int | None = None
        mp_override: int | None = None
        mov_override: int | None = None
        armor_override: int = 0
        db_override: str | None = None
        build_override: int | None = None

        text = npc_text.strip()

        # ── Name extraction ──
        # Check for explicit name prefixes
        name_prefixes = ["名称:", "姓名:", "名字:", "name:", "npc名:", "npc名称:"]
        for prefix in name_prefixes:
            if text.lower().startswith(prefix.lower()):
                rest = text[len(prefix):].lstrip()
                # Name is everything up to the first newline or comma-period
                m = re.match(r'([^\n，,。.]+)', rest)
                if m:
                    name = m.group(1).strip()
                    text = rest[m.end():].strip()
                break
        else:
            # If first line contains Chinese attribute keywords, it's not a name line
            first_line = text.split("\n")[0].strip()
            cn_attr_kw = ["力量", "体质", "体型", "敏捷", "智力", "外貌", "意志", "教育", "幸运", "理智", "生命"]
            has_cn_attr = any(kw in first_line for kw in cn_attr_kw)
            has_en_attr = bool(re.search(r'\b(STR|CON|DEX|APP|POW|SIZ|INT|EDU|LUCK)\s*\d+', first_line, re.IGNORECASE))
            if not has_cn_attr and not has_en_attr:
                # First line is name/description: "梅洛迪亚斯·杰弗逊 58岁，守墓人"
                # Extract name (before age/occupation markers)
                name_match = re.match(r'^(.+?)(?:\s+\d+岁|\s*[，,]\s*\S+)?$', first_line)
                if name_match:
                    name = name_match.group(1).strip()
                    text = text[len(first_line):].strip()
                    # Try to extract age and occupation from the same line
                    age_m = re.search(r'(\d+)\s*岁', first_line)
                    occ_m = re.search(r'[，,]\s*(.+?)$', first_line)
                    if age_m:
                        background_parts.append(f"年龄: {age_m.group(1)}")
                    if occ_m:
                        occupation = occ_m.group(1).strip()

        # Section splitting
        skill_section = ""
        weapon_section = ""
        bg_section = ""

        # Try to split by section markers
        section_markers = [
            (r'技能[：:]', 'skills'),
            (r'武器[：:]', 'weapons'),
            (r'背景[：:]', 'background'),
            (r'装备[：:]', 'weapons'),
            (r'描述[：:]', 'background'),
        ]

        remaining = text
        sections: list[tuple[str, str]] = []  # (type, content)
        current_type = "attrs"
        current_content: list[str] = []

        for line in text.split("\n"):
            line_stripped = line.strip()
            if not line_stripped:
                continue
            matched = False
            for pattern, stype in section_markers:
                m = re.match(pattern, line_stripped, re.IGNORECASE)
                if m:
                    if current_content:
                        sections.append((current_type, "\n".join(current_content)))
                    current_type = stype
                    current_content = [line_stripped[m.end():].strip()] if line_stripped[m.end():].strip() else []
                    matched = True
                    break
            if not matched:
                current_content.append(line_stripped)
        if current_content:
            sections.append((current_type, "\n".join(current_content)))

        for stype, content in sections:
            if stype == "attrs":
                # Parse English attribute values: STR 70 CON 60 DEX 50 etc.
                attr_pattern_en = re.compile(r'\b(STR|CON|DEX|APP|POW|SIZ|INT|EDU|LUCK)\s*[：:=\s]*\s*(\d{1,3})\b', re.IGNORECASE)
                for m in attr_pattern_en.finditer(content):
                    key = m.group(1).upper()
                    val = int(m.group(2))
                    if 1 <= val <= 999:
                        attrs[key] = val

                # Parse Chinese attribute values: 力量 45 体质 65 体型 60 etc.
                cn_attr_map = {
                    "力量": "STR", "体质": "CON", "体型": "SIZ", "敏捷": "DEX",
                    "智力": "INT", "外貌": "APP", "意志": "POW", "教育": "EDU",
                    "幸运": "LUCK", "灵感": "INT",
                }
                for cn_name, en_key in cn_attr_map.items():
                    # Pattern: 力量 45 or 力量45 or 力量:45
                    for m in re.finditer(re.escape(cn_name) + r'\s*[：:=\s]*\s*(\d{1,3})', content):
                        val = int(m.group(1))
                        if 1 <= val <= 999:
                            attrs[en_key] = val

                # Parse HP/SAN/MP/MOV/Armor overrides (English + Chinese)
                for m in re.finditer(r'\b(?:HP|生命值?)\s*[：:=\s]*\s*(\d{1,4})\b', content, re.IGNORECASE):
                    hp_override = int(m.group(1))
                for m in re.finditer(r'\b(?:SAN|理智值?|理智)\s*[：:=\s]*\s*(\d{1,4})\b', content, re.IGNORECASE):
                    san_override = int(m.group(1))
                for m in re.finditer(r'\b(?:MP|魔法值?)\s*[：:=\s]*\s*(\d{1,4})\b', content, re.IGNORECASE):
                    mp_override = int(m.group(1))
                for m in re.finditer(r'\b(?:MOV|移动速度?|移动)\s*[：:=\s]*\s*(\d{1,2})\b', content, re.IGNORECASE):
                    mov_override = int(m.group(1))
                for m in re.finditer(r'(?:护甲|装甲|ARMOR?)\s*[：:=\s]*\s*(\d{1,2})\b', content, re.IGNORECASE):
                    armor_override = int(m.group(1))
                for m in re.finditer(r'\b(DB|伤害加值)\s*[：:=\s]*\s*([+-]?\d{1,2}[dD]\d{1,2}|[+-]?\d+)\b', content, re.IGNORECASE):
                    db_override = m.group(2)
                for m in re.finditer(r'\bBUILD\s*[：:=\s]*\s*(\d{1,2})\b', content, re.IGNORECASE):
                    build_override = int(m.group(1))

                # Parse age: 58岁 or 年龄: 58
                age_m = re.search(r'(?:年龄|岁数)?\s*[：:=\s]*\s*(\d{1,3})\s*岁', content)
                if age_m:
                    background_parts.append(f"年龄: {age_m.group(1)}")

                # Parse occupation
                occ_m = re.search(r'(?:职业|OCCUPATION)\s*[：:=\s]*\s*(.+?)$', content, re.IGNORECASE | re.MULTILINE)
                if occ_m:
                    occupation = occ_m.group(1).strip()

            elif stype == "skills":
                # Parse skills: 技能名 数值, 技能名 数值
                skill_parts = re.split(r'[,，;；\n]', content)
                for part in skill_parts:
                    part = part.strip()
                    if not part:
                        continue
                    # Match: name number (number may contain parentheses like "格斗(斗殴) 60")
                    sm = re.match(r'(.+?)\s+(\d{1,3})\s*$', part)
                    if sm:
                        sname = sm.group(1).strip()
                        sval = int(sm.group(2))
                        if 0 <= sval <= 999:
                            skills.append({
                                "name": sname,
                                "value": sval,
                                "half": sval // 2,
                                "fifth": sval // 5,
                            })

            elif stype == "weapons":
                # Parse weapons: 武器名 伤害表达式
                wp_lines = re.split(r'[\n;；]', content)
                for wp_line in wp_lines:
                    wp_line = wp_line.strip()
                    if not wp_line:
                        continue
                    # Match: name damage (e.g., "匕首 1d4+2" or "拳头 1d3")
                    wm = re.match(r'(.+?)\s+((?:\d+[dD]\d+(?:[+-]\d+)?)|(?:\d+))\s*$', wp_line)
                    if wm:
                        wname = wm.group(1).strip()
                        wdamage = wm.group(2).strip()
                        # Guess skill from weapon name
                        wskill = "格斗(斗殴)"
                        wname_lower = wname.lower()
                        if any(kw in wname_lower for kw in ["拳", "爪", "牙", "咬"]):
                            wskill = "格斗(斗殴)"
                        elif any(kw in wname_lower for kw in ["刀", "剑", "匕首", "矛", "枪", "棍", "斧", "锤"]):
                            wskill = wname if wname else "格斗(斗殴)"
                        elif any(kw in wname_lower for kw in ["弓", "弩", "箭"]):
                            wskill = "射击"
                        elif any(kw in wname_lower for kw in ["手枪", "步枪", "霰弹", "冲锋枪"]):
                            wskill = "射击"
                        weapons.append({
                            "name": wname,
                            "damage": wdamage,
                            "skill": wskill if wskill else "格斗(斗殴)",
                        })
                    else:
                        # Just a weapon name without damage
                        weapons.append({
                            "name": wp_line,
                            "damage": "1d3",
                            "skill": "格斗(斗殴)",
                        })

            elif stype == "background":
                background_parts.append(content)

        # Build background
        background_dict: dict[str, str] = {}
        if background_parts:
            bg_text = "\n".join(background_parts)
            # Simple key-value parsing
            for line in bg_text.split("\n"):
                if "：" in line or ":" in line:
                    parts = re.split(r'[：:]', line, maxsplit=1)
                    if len(parts) == 2:
                        background_dict[parts[0].strip()] = parts[1].strip()
                else:
                    background_dict.setdefault("描述", "")
                    background_dict["描述"] += line + "\n"
            background_dict = {k: v.strip() for k, v in background_dict.items() if v.strip()}

        if not skills:
            skills.append({"name": "闪避", "value": attrs["DEX"] // 2, "half": attrs["DEX"] // 4, "fifth": attrs["DEX"] // 10})

        if not weapons:
            weapons.append({"name": "拳头", "damage": "1d3", "skill": "拳头/摔跌"})

        # Calculate derived values
        con, siz = attrs["CON"], attrs["SIZ"]
        pow_val, dex = attrs["POW"], attrs["DEX"]
        hp_val = hp_override if hp_override is not None else max(1, (con + siz) // 10)
        san_val = san_override if san_override is not None else pow_val
        mp_val = mp_override if mp_override is not None else max(1, pow_val // 5)
        mov_val = mov_override if mov_override is not None else 7
        if dex < siz and mov_override is None:
            mov_val = 7
        elif dex > siz and mov_override is None:
            mov_val = 8

        # Build character dict
        attributes_list = [
            {"key": k, "label": v, "value": attrs[k], "half": attrs[k] // 2, "fifth": attrs[k] // 5}
            for k, v in label_map.items()
        ]

        character = {
            "basic": {"name": f"{name} (NPC)", "occupation": occupation},
            "attributes": attributes_list,
            "status": {"hp": hp_val, "san": san_val, "mp": mp_val, "mov": mov_val, "armor": armor_override},
            "initialStatus": {"hp": hp_val, "san": san_val, "mp": mp_val, "mov": mov_val, "armor": armor_override},
            "skills": skills,
            "weapons": weapons,
            "background": background_dict,
            "experiences": [],
            "spells": [],
            "warnings": [],
            "sourceFileName": f"npc-{name}",
            "isNpc": True,
        }

        return self.add_character(room_id, keeper_id, character, replace_existing=False)

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
            if room_id in self._rooms:
                del self._rooms[room_id]
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
        if not self.path.exists():
            return {"rooms": {}}

        try:
            with self.path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except json.JSONDecodeError:
            return {"rooms": {}}

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

    # ── Combat ──

    def _compute_db(self, str_val: int, siz_val: int) -> tuple:
        total = str_val + siz_val
        if total <= 64: return ("-2", -2)
        if total <= 84: return ("-1", -1)
        if total <= 124: return ("0", 0)
        if total <= 164: return ("+1D4", 1)
        if total <= 204: return ("+1D6", 2)
        if total <= 284: return ("+2D6", 3)
        if total <= 364: return ("+3D6", 4)
        return ("+4D6", 5)

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

    def get_combat_state(self, room_id: str) -> dict | None:
        with self._lock:
            room = self._require_room(room_id)
            cs = room.get("combatState")
            return deepcopy(cs) if cs else None

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

    def _is_impaling_weapon(self, weapon: dict | None) -> bool:
        """Detect if a weapon is impaling based on its name (COC 7e CRB p104)."""
        if not weapon:
            return False
        name = (weapon.get("name") or "").lower()
        impaling_keywords = ["剑", "矛", "刺", "匕首", "小刀", "刀", "枪", "箭", "弩",
                             "sword", "spear", "knife", "dagger", "blade", "bayonet",
                             "rapier", "lance", "pike", "javelin"]
        return any(kw in name for kw in impaling_keywords)

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

    def _max_damage(self, expr: str) -> int:
        import re
        m = re.match(r'(\d*)[dD](\d+)\s*([+-]\s*\d+)?', expr.strip())
        if not m:
            return 0
        count = int(m.group(1)) if m.group(1) else 1
        sides = int(m.group(2))
        modifier = int(m.group(3).replace(' ', '')) if m.group(3) else 0
        return count * sides + modifier

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

    # ── Chase ──

    def start_chase(self, room_id: str, editor_id: str) -> dict:
        with self._lock:
            room = self._require_room(room_id)
            editor = self._find_member(room, editor_id)
            if editor["role"] != "keeper":
                raise PermissionError("Only keeper can start chase")

            participants = []
            for member in room["members"]:
                if member["role"] == "spectator":
                    continue
                char = next((c for c in room.get("characters", [])
                           if c.get("ownerId") == member["id"] and c.get("active") is not False), None)
                mov = (char.get("status") or {}).get("mov") or 7 if char else 7
                participants.append({
                    "memberId": member["id"],
                    "characterId": char["id"] if char else "",
                    "displayName": char.get("basic", {}).get("name") if char else member["displayName"],
                    "mov": mov,
                    "role": "fugitive" if member["role"] != "keeper" else "pursuer",
                    "position": 2 if member["role"] != "keeper" else 0,
                })

            chase_state = {
                "active": True,
                "participants": participants,
                "obstacles": [],
                "createdAt": self._now(),
            }
            room["chaseState"] = chase_state
            self._add_system_message(room, f"{editor['displayName']} 开始了追逐轮次！")
            self._save()
            return deepcopy(chase_state)

    def get_chase_state(self, room_id: str) -> dict | None:
        with self._lock:
            room = self._require_room(room_id)
            cs = room.get("chaseState")
            return deepcopy(cs) if cs else None

    def act_chase(self, room_id: str, participant_id: str, action_type: str,
                  weapon_index: int | None, hidden: bool) -> dict:
        from app.modules.dice.roller import roll_dice
        with self._lock:
            room = self._require_room(room_id)
            cs = room.get("chaseState")
            if not cs or not cs.get("active"):
                raise ValueError("No active chase")

            participant = next((p for p in cs["participants"]
                               if p["memberId"] == participant_id), None)
            if not participant:
                raise ValueError("Participant not found")

            if action_type == "speed_check":
                # CON roll to adjust MOV
                member = self._find_member(room, participant_id)
                char = next((c for c in room.get("characters", [])
                           if c.get("ownerId") == participant_id), None)
                con_value = 50
                if char:
                    for attr in char.get("attributes", []):
                        if attr.get("key") == "CON":
                            con_value = attr.get("value") or 50
                            break
                result = roll_dice("1d100", target_value=con_value, bonus_penalty=0)
                sl = result.get("successLevel")
                if sl in ("critical", "extreme", "hard", "regular"):
                    if result.get("successLevel") == "extreme":
                        participant["mov"] += 1
                else:
                    participant["mov"] = max(1, participant["mov"] - 1)

                roll_record = {
                    "expression": "1d100", "total": result["total"],
                    "breakdown": result.get("breakdown", []),
                    "targetValue": con_value, "bonusPenalty": 0,
                    "successLevel": result.get("successLevel"),
                    "successLabel": result.get("successLabel"),
                    "isSuccess": sl in ("critical", "extreme", "hard", "regular"),
                    "hidden": hidden,
                    "label": f"🏃 {participant['displayName']} 速度检定 CON={con_value} MOV={participant['mov']}",
                }
                self.add_dice_roll(room_id, participant_id, roll_record)

            elif action_type == "maneuver":
                participant["position"] += participant.get("mov", 7)
                self._add_system_message(room,
                    f"🏃 {participant['displayName']} 移动到位置 {participant['position']}")

            elif action_type == "conflict":
                result = roll_dice("1d100")
                sl = result.get("successLevel")
                roll_record = {
                    "expression": "1d100", "total": result["total"],
                    "breakdown": result.get("breakdown", []),
                    "targetValue": None, "bonusPenalty": 0,
                    "successLevel": sl, "successLabel": None,
                    "isSuccess": sl in ("critical", "extreme", "hard", "regular") if sl else None,
                    "hidden": hidden,
                    "label": f"💥 {participant['displayName']} 追逐冲突检定",
                }
                self.add_dice_roll(room_id, participant_id, roll_record)

            self._save()
            return deepcopy(cs)

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

    def cleanup_empty_rooms(self, max_idle_seconds: int = 30) -> int:
        """Remove rooms that have had zero online members for more than max_idle_seconds.
        Returns the number of rooms removed."""
        with self._lock:
            now = datetime.now(timezone.utc)
            to_remove = []
            for room_id, room in self._state.get("rooms", {}).items():
                has_online = any(m.get("online") for m in room.get("members", []))
                if has_online:
                    continue
                # Use the latest activity timestamp: last message, last roll, last voice,
                # or fall back to room creation time.
                latest_ts = room.get("createdAt", "")
                for msg in room.get("messages", []):
                    ts = msg.get("createdAt", "")
                    if ts and ts > latest_ts:
                        latest_ts = ts
                for roll in room.get("rolls", []):
                    ts = roll.get("createdAt", "")
                    if ts and ts > latest_ts:
                        latest_ts = ts
                for voice in room.get("voices", []):
                    ts = voice.get("createdAt", "")
                    if ts and ts > latest_ts:
                        latest_ts = ts
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
                # Clean up orphaned voice files
                upload_dir = self.data_dir / "uploads" / rid
                if upload_dir.exists():
                    try:
                        shutil.rmtree(upload_dir)
                    except OSError:
                        pass
            if to_remove:
                self._save()
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