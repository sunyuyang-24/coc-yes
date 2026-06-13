"""Combat round management for RoomStore (mixin)."""

from __future__ import annotations

from copy import deepcopy


class CombatMixin:
    """Combat methods mixed into RoomStore. Expects self to provide:
    _lock, _save(), _require_room(), _find_member(), _find_character(),
    _add_system_message(), add_dice_roll(), _now().
    """

    @staticmethod
    def _compute_db(str_val: int, siz_val: int) -> tuple:
        total = str_val + siz_val
        if total <= 64: return ("-2", -2)
        if total <= 84: return ("-1", -1)
        if total <= 124: return ("0", 0)
        if total <= 164: return ("+1D4", 1)
        if total <= 204: return ("+1D6", 2)
        if total <= 284: return ("+2D6", 3)
        if total <= 364: return ("+3D6", 4)
        return ("+4D6", 5)

    @staticmethod
    def _is_impaling_weapon(weapon: dict | None) -> bool:
        if not weapon:
            return False
        name = (weapon.get("name") or "").lower()
        impaling_keywords = ["剑", "矛", "刺", "匕首", "小刀", "刀", "枪", "箭", "弩",
                             "sword", "spear", "knife", "dagger", "blade", "bayonet",
                             "rapier", "lance", "pike", "javelin"]
        return any(kw in name for kw in impaling_keywords)

    @staticmethod
    def _max_damage(expr: str) -> int:
        import re
        m = re.match(r'(\d*)[dD](\d+)\s*([+-]\s*\d+)?', expr.strip())
        if not m:
            return 0
        count = int(m.group(1)) if m.group(1) else 1
        sides = int(m.group(2))
        modifier = int(m.group(3).replace(' ', '')) if m.group(3) else 0
        return count * sides + modifier

    def _calc_damage(self, weapon_damage: str, db: str, success_level: str | None,
                     is_impaling: bool = False, is_fighting_back: bool = False) -> int:
        from app.modules.dice.roller import roll_dice
        db_expr = db.lstrip("+") if db else db
        wd = roll_dice(weapon_damage)["total"]
        db_val = roll_dice(db_expr)["total"] if db_expr and db_expr not in ("0", "-1", "-2") else (
            int(db_expr) if db_expr and db_expr.lstrip('-').isdigit() else 0)
        if success_level in ("extreme", "critical"):
            max_wd = self._max_damage(weapon_damage)
            max_db_val = self._max_damage(db_expr) if db_expr and db_expr not in ("0", "-1", "-2") else 0
            if is_impaling and not is_fighting_back:
                return max_wd + max_db_val + wd
            return max_wd + max_db_val
        return max(0, wd + db_val)

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

            weapons = attacker_char.get("weapons", [])
            weapon = weapons[weapon_index] if 0 <= weapon_index < len(weapons) else None
            weapon_name = weapon.get("name", "徒手") if weapon else "徒手"
            weapon_damage = str(weapon.get("damage", "1D3")) if weapon else "1D3"
            weapon_skill_name = str(weapon.get("skill", "格斗(斗殴)")) if weapon else "格斗(斗殴)"
            is_impaling = self._is_impaling_weapon(weapon)

            attacker_skills = attacker_char.get("skills", [])
            skill_value = 50
            for sk in attacker_skills:
                if sk.get("name") == weapon_skill_name:
                    skill_value = sk.get("value") or 50
                    break

            attack_roll = roll_dice("1d100", target_value=skill_value, bonus_penalty=0)

            if action_type == "dodge":
                defender_skills = defender_char.get("skills", [])
                dodge_value = 25
                for sk in defender_skills:
                    if sk.get("name") == "闪避":
                        dodge_value = sk.get("value") or 25
                        break
                defend_roll = roll_dice("1d100", target_value=dodge_value, bonus_penalty=0)
                winner = opposed_check(attack_roll["total"], skill_value,
                                      defend_roll["total"], dodge_value,
                                      defender_wins_tie=True)
                attacker_wins = winner.get("winner") == "actor"
                if attacker_wins:
                    damage = self._calc_damage(weapon_damage, current_actor["db"],
                                              attack_roll.get("successLevel"),
                                              is_impaling=is_impaling, is_fighting_back=False)
                    new_hp = max(0, defender_actor["hp"] - damage)
                    defender_actor["hp"] = new_hp
                    defender_char.setdefault("status", {})["hp"] = new_hp
                    self._add_system_message(room,
                        f"⚔️ [闪避失败] {current_actor['displayName']} 用{weapon_name}攻击"
                        f"{defender_actor['displayName']}（{defend_roll['total']}/{dodge_value} 闪避检定未通过），"
                        f"造成 {damage} 点伤害！HP → {defender_actor['hp']}")
                    if damage >= defender_actor["hpMax"] // 2:
                        self._add_system_message(room,
                            f"💀 {defender_actor['displayName']} 受到重伤！")
                else:
                    self._add_system_message(room,
                        f"💨 [闪避成功] {defender_actor['displayName']} 闪避了 {current_actor['displayName']} "
                        f"用{weapon_name}的攻击（{defend_roll['total']}/{dodge_value}）")

            elif action_type == "fight_back":
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
                                              is_impaling=is_impaling, is_fighting_back=True)
                    new_hp = max(0, defender_actor["hp"] - damage)
                    defender_actor["hp"] = new_hp
                    defender_char.setdefault("status", {})["hp"] = new_hp
                    self._add_system_message(room,
                        f"⚔️ [反击失败] {current_actor['displayName']} 用{weapon_name}攻击"
                        f"{defender_actor['displayName']}（反击检定未通过），造成 {damage} 点伤害！HP → {new_hp}")
                    if damage >= defender_actor["hpMax"] // 2:
                        self._add_system_message(room, f"💀 {defender_actor['displayName']} 受到重伤！")
                else:
                    def_is_impaling = self._is_impaling_weapon(defender_weapon)
                    counter_damage = self._calc_damage(defender_weapon_damage, defender_actor.get("db", "0"),
                                                       defend_roll.get("successLevel"),
                                                       is_impaling=def_is_impaling, is_fighting_back=True)
                    new_hp = max(0, current_actor["hp"] - counter_damage)
                    current_actor["hp"] = new_hp
                    attacker_char.setdefault("status", {})["hp"] = new_hp
                    def_wname = (defender_weapon.get("name") if defender_weapon else "徒手") or "徒手"
                    self._add_system_message(room,
                        f"🛡️ [反击成功] {defender_actor['displayName']} 反击 {current_actor['displayName']}，"
                        f"用{def_wname}造成 {counter_damage} 点伤害！HP → {new_hp}")
                    if counter_damage >= current_actor["hpMax"] // 2:
                        self._add_system_message(room, f"💀 {current_actor['displayName']} 受到重伤！")

            elif action_type == "attack":
                atk_success = attack_roll.get("successLevel") in ("critical", "extreme", "hard", "regular")
                if atk_success:
                    damage = self._calc_damage(weapon_damage, current_actor["db"],
                                              attack_roll.get("successLevel"),
                                              is_impaling=is_impaling, is_fighting_back=False)
                    new_hp = max(0, defender_actor["hp"] - damage)
                    defender_actor["hp"] = new_hp
                    defender_char.setdefault("status", {})["hp"] = new_hp
                    self._add_system_message(room,
                        f"⚔️ [直接攻击] {current_actor['displayName']} 用{weapon_name}"
                        f"命中 {defender_actor['displayName']}，造成 {damage} 点伤害！HP → {new_hp}")
                    if damage >= defender_actor["hpMax"] // 2:
                        self._add_system_message(room, f"💀 {defender_actor['displayName']} 受到重伤！")
                else:
                    self._add_system_message(room,
                        f"❌ [直接攻击] {current_actor['displayName']} 用{weapon_name}攻击"
                        f"{defender_actor['displayName']}，未命中（{attack_roll['total']}/{skill_value}）")
            else:
                # Maneuver
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

            current_actor["hasActedThisRound"] = True

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

            cs["currentActorIndex"] += 1
            if cs["currentActorIndex"] >= len(actors):
                cs["roundNumber"] += 1
                cs["currentActorIndex"] = 0
                for a in actors:
                    a["hasActedThisRound"] = False
                self._add_system_message(room, f"🔄 Round {cs['roundNumber']} 开始！")

            self._save()
            return deepcopy(cs)

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
