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

            self._add_system_message(room, f"{keeper_name} 创建了房间。")
            self._save()
            return deepcopy(room), keeper_id

    def join_room(self, invite_code: str, display_name: str, password: str | None = None, role: str = "player") -> tuple[dict, str]:
        with self._lock:
            room = self._find_by_invite(invite_code)
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
        """返回对指定成员过滤后的房间数据。非 KP 成员看不到暗骰细节和私密消息。"""
        with self._lock:
            room = deepcopy(self._require_room(room_id))
        member = self._find_member(room, member_id)
        is_keeper = member["role"] == "keeper"

        # 过滤聊天消息中的私密消息
        room["messages"] = [
            m for m in room.get("messages", [])
            if not m.get("privateTo") or m.get("privateTo") == member_id or m.get("senderId") == member_id or is_keeper
        ]

        # 过滤投掷详情：非 KP 看暗骰只显示 hidden=true, total=null
        if not is_keeper and "rolls" in room:
            for roll in room["rolls"]:
                if roll.get("hidden"):
                    roll["total"] = None
                    roll["breakdown"] = []
                    roll["successLevel"] = None
                    roll["successLabel"] = None

        # 过滤聊天中暗骰消息的敏感数据
        for msg in room.get("messages", []):
            if msg.get("type") == "dice_roll" and msg.get("roll") and msg["roll"].get("hidden") and not is_keeper:
                msg["roll"]["total"] = None
                msg["roll"]["breakdown"] = []
                msg["roll"]["successLevel"] = None
                msg["roll"]["successLabel"] = None

        return room

    def add_message(self, room_id: str, sender_id: str | None, content: str, reply_to: dict | None = None, msg_type: str = "text", private_to: str | None = None, whisper_to: str | None = None, mention_ids: list[str] | None = None) -> dict:
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
            "basic": {"name": name, "occupation": "NPC"},
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
        from app.modules.dice.roller import roll_dice
        with self._lock:
            room = self._require_room(room_id)
            roller = self._find_member(room, roller_id)
            character = self._find_character(room, character_id)
            current_san = (character.get("status") or {}).get("san") or 0

            # Roll 1d100 vs current SAN
            dice_result = roll_dice("1d100", target_value=current_san, bonus_penalty=0)
            success_level = dice_result.get("successLevel")
            is_success = success_level in ("critical", "extreme", "hard", "regular")

            # Parse loss expression
            loss_expr = success_loss if is_success else failure_loss
            loss_amount = self._parse_loss(loss_expr)

            # Update character SAN
            new_san = max(0, current_san - loss_amount)
            character.setdefault("status", {})["san"] = new_san

            # Record result
            loss_str = f"{success_loss if is_success else failure_loss} → SAN -{loss_amount}"
            label = f"{character.get('basic', {}).get('name', '??')} SAN CHECK (当前SAN={current_san})"
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
                "isSuccess": is_success,
                "triggersInsanity": loss_amount >= 5,
            }

            # System message for SAN change
            self._add_system_message(
                room,
                f"{character.get('basic', {}).get('name', '??')} SAN CHECK "
                f"{'成功' if is_success else '失败'}，SAN {current_san} → {new_san} "
                f"({'-' if loss_amount > 0 else ''}{loss_amount})"
                + (" [触发临时疯狂检定]" if loss_amount >= 5 else "")
            )

            self._save()
            return result

    def _parse_loss(self, expr: str) -> int:
        """Parse a SAN loss expression like '1', '1D6', '1D4+1' and return the rolled value."""
        import re
        from app.modules.dice.roller import roll_dice
        expr = expr.strip().upper()
        if re.match(r'^\d+$', expr):
            return int(expr)
        # Use the dice roller for expressions like 1D6, 2D10+1, etc.
        result = roll_dice(expr)
        return result["total"]

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
                # Opposed: attack vs dodge
                winner = opposed_check(attack_roll["total"], skill_value,
                                      defend_roll["total"], dodge_value)
                attacker_wins = winner.get("winner") == "actor"
                if attacker_wins:
                    # Apply damage
                    damage = self._calc_damage(weapon_damage, current_actor["db"],
                                              attack_roll.get("successLevel"))
                    new_hp = max(0, defender_actor["hp"] - damage)
                    defender_actor["hp"] = new_hp
                    defender_char.setdefault("status", {})["hp"] = new_hp
                    self._add_system_message(room,
                        f"⚔️ {current_actor['displayName']} 用{weapon_name}攻击"
                        f"{defender_actor['displayName']}（{defend_roll['total']}/{dodge_value} 闪避失败），"
                        f"造成 {damage} 点伤害！HP {defender_actor['hp']}")
                    # Check major wound
                    if damage >= defender_actor["hpMax"] // 2:
                        self._add_system_message(room,
                            f"💀 {defender_actor['displayName']} 受到重伤！")
                else:
                    self._add_system_message(room,
                        f"💨 {defender_actor['displayName']} 闪避了 {current_actor['displayName']} 的攻击"
                        f"（{defend_roll['total']}/{dodge_value}）")
            else:
                # Fight back or maneuver
                defender_skills = defender_char.get("skills", [])
                fight_value = 25
                for sk in defender_skills:
                    if sk.get("name") in ("格斗(斗殴)", "格斗(斗殴)"):
                        fight_value = sk.get("value") or 25
                        break
                defend_roll = roll_dice("1d100", target_value=fight_value, bonus_penalty=0)
                winner = opposed_check(attack_roll["total"], skill_value,
                                      defend_roll["total"], fight_value)
                attacker_wins = winner.get("winner") == "actor"
                if attacker_wins:
                    damage = self._calc_damage(weapon_damage, current_actor["db"],
                                              attack_roll.get("successLevel"))
                    new_hp = max(0, defender_actor["hp"] - damage)
                    defender_actor["hp"] = new_hp
                    defender_char.setdefault("status", {})["hp"] = new_hp
                    self._add_system_message(room,
                        f"⚔️ {current_actor['displayName']} 用{weapon_name}攻击"
                        f"{defender_actor['displayName']}，造成 {damage} 点伤害！HP → {new_hp}")
                    if damage >= defender_actor["hpMax"] // 2:
                        self._add_system_message(room,
                            f"💀 {defender_actor['displayName']} 受到重伤！")
                else:
                    self._add_system_message(room,
                        f"🛡️ {defender_actor['displayName']} 反击了 {current_actor['displayName']} 的攻击")

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

    def _calc_damage(self, weapon_damage: str, db: str, success_level: str | None) -> int:
        from app.modules.dice.roller import roll_dice
        wd = roll_dice(weapon_damage)["total"]
        db_val = roll_dice(db)["total"] if db and db not in ("0", "-1", "-2") else (
            int(db) if db and db.lstrip('-').isdigit() else 0)
        # Extreme success = max damage
        if success_level == "extreme":
            max_wd = self._max_damage(weapon_damage)
            max_db_val = self._max_damage(db) if db and db not in ("0", "-1", "-2") else 0
            return max_wd + max_db_val + wd  # impale rule
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