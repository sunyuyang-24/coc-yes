"""Chase round management for RoomStore (mixin)."""

from __future__ import annotations

from copy import deepcopy


class ChaseMixin:
    """Chase methods mixed into RoomStore. Expects self to provide:
    _lock, _save(), _require_room(), _find_member(), _add_system_message(),
    add_dice_roll(), _now().
    """

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
