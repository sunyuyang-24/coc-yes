"""Combat round management for RoomStore (mixin) — COC 7e Melee.

New model (replaces the legacy actor/memberId system):
- Participants are identified by characterId, with a controllerMemberId for
  permission checks. A KP simultaneously controls all NPCs and their own
  character card.
- Each round has two phases: declaration (intents) → resolution (defenses
  then dice roll / damage).
- Only the KP can move from declaration to resolution by locking the round
  (`lock_combat_intents`). Players submit their own intents and defenses;
  KP can override or set values on any participant.
- The defender can react at most once per attacking intent during the same
  round; once a reaction (dodge / fight_back / maneuver) has been consumed
  for the current attacker, a subsequent attacker targeting the same
  defender gets +1 bonus die ("寡不敌众").
- During resolve the intents are processed in descending order of the
  attacker's DEX so high-DEX characters act first each round.
- Damage model:
  - normal: weapon roll + DB, armor subtracted from total.
  - extreme success (non-impaling): max(weapon) + DB.
  - impale (critical or extreme success on impaling weapon):
    max(weapon) + max(DB) + another rolled weapon damage (armor applies
    only once).
- Status transitions:
  - active → major_wound (single damage >= hpMax/2)
  - any → unconscious (HP reaches 0 at any moment, even without major
    wound; also, CON failing on major wound if HP > 0)
  - unconscious + HP = 0 → dying (HP was already 0 from another wound, OR
    the hit that put character at HP 0 was a major wound simultaneously)
  - dying → dead (a later hit while dying; or manual KP action)
  - damage >= hpMax in a single hit → instant dead.
- Dodges default to the character's "闪避" skill value; when missing they
  fall back to DEX/2 (not DEX*2).
"""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import timezone, datetime

from app.modules.characters.constants import compute_db_build


# ── small helpers ───────────────────────────────────────────────────

_IMPALING_KEYWORDS = [
    "剑", "矛", "刺", "匕首", "小刀", "刀", "枪", "箭", "弩",
    "sword", "spear", "knife", "dagger", "blade", "bayonet",
    "rapier", "lance", "pike", "javelin",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_attribute(char: dict, key: str) -> int:
    attrs = char.get("attributes", []) or []
    for a in attrs:
        if a.get("key") == key:
            val = a.get("value")
            if val is not None:
                return int(val)
    return 50


def _get_skill_value(char: dict, skill_name: str, default: int = 25) -> int:
    skills = char.get("skills", []) or []
    for sk in skills:
        if sk.get("name") == skill_name:
            val = sk.get("value")
            if val is not None:
                return int(val)
    return default


def _get_weapon(char: dict, weapon_index: int | None) -> dict | None:
    weapons = char.get("weapons", []) or []
    if weapon_index is None or weapon_index < 0 or weapon_index >= len(weapons):
        return None
    w = weapons[weapon_index]
    return w if w else None


def _is_impaling_weapon(weapon: dict | None) -> bool:
    if not weapon:
        return False
    name = (weapon.get("name") or "").lower()
    return any(kw in name for kw in _IMPALING_KEYWORDS)


def _get_weapon_skill_value(char: dict, weapon: dict | None) -> int:
    if weapon and weapon.get("value"):
        return int(weapon["value"])
    skill_name = weapon.get("skill") if weapon else None
    if skill_name:
        return _get_skill_value(char, skill_name, default=25)
    # bare-fist default
    return _get_skill_value(char, "格斗(斗殴)", default=25)


def _get_weapon_damage_expr(weapon: dict | None) -> str:
    if weapon and weapon.get("damage"):
        return str(weapon["damage"])
    return "1D3"  # bare fist default


def _get_dodge_value(char: dict) -> int:
    """COC 7e: Dodge default is DEX/2 (not DEX*2)."""
    skills = char.get("skills", []) or []
    for sk in skills:
        name = sk.get("name") or ""
        if name in ("闪避", "躲闪", "Dodge", "dodge"):
            val = sk.get("value")
            if val is not None:
                return int(val)
    dex = _get_attribute(char, "DEX")
    return max(1, dex // 2)


def _get_maneuver_resist(char: dict) -> int:
    """Maneuver uses STR/DEX/SIZ highest."""
    return max(
        _get_attribute(char, "STR"),
        _get_attribute(char, "DEX"),
        _get_attribute(char, "SIZ"),
    )


def _get_armor(char: dict) -> int:
    status = char.get("status", {}) or {}
    val = status.get("armor")
    if val is None:
        initial = char.get("initialStatus", {}) or {}
        val = initial.get("armor")
    return int(val) if val is not None else 0


def _get_db_and_build(char: dict) -> tuple[str, int]:
    status = char.get("status", {}) or {}
    initial = char.get("initialStatus", {}) or {}
    db_str = status.get("damageBonus") or initial.get("damageBonus")
    build_val = status.get("build") or initial.get("build")
    if db_str is not None and build_val is not None:
        return str(db_str), int(build_val)
    str_val = _get_attribute(char, "STR")
    siz_val = _get_attribute(char, "SIZ")
    computed_db, computed_build = compute_db_build(str_val, siz_val)
    return computed_db, computed_build


def _get_hp(char: dict) -> tuple[int, int]:
    status = char.get("status", {}) or {}
    initial = char.get("initialStatus", {}) or {}
    hp_cur = status.get("hp")
    hp_max = initial.get("hp") or status.get("hp") or 10
    if hp_cur is None:
        hp_cur = hp_max
    return int(hp_cur), int(hp_max)


def _max_damage(expr: str) -> int:
    """Interpret a dice / constant expression as its maximum possible value.

    Accepted forms: "1D4+1", "2d6", "+1D4", "0", "-1".
    """
    if not expr:
        return 0
    s = expr.strip().replace(" ", "").lower()
    if s.startswith("+"):
        s = s[1:]
    if s.lstrip("-").isdigit():
        return int(s)
    import re as _re
    m = _re.match(r"^(\d*)d(\d+)([+-]\d+)?$", s)
    if not m:
        return 0
    count = int(m.group(1)) if m.group(1) else 1
    sides = int(m.group(2))
    modifier = int(m.group(3)) if m.group(3) else 0
    return count * sides + modifier


_SUCCESS_ORDER = {
    "fumble": 0,
    "failure": 1,
    "regular": 2,
    "hard": 3,
    "extreme": 4,
    "critical": 5,
}


def _roll_succeeded(roll: dict) -> bool:
    return _SUCCESS_ORDER.get(roll.get("successLevel"), 0) >= 2


def _combat_opposed_winner(
    attack_roll: dict,
    defense_roll: dict,
    defense_type: str,
) -> str:
    attack_order = _SUCCESS_ORDER.get(attack_roll.get("successLevel"), 0)
    defense_order = _SUCCESS_ORDER.get(defense_roll.get("successLevel"), 0)
    if attack_order > defense_order:
        return "actor"
    if defense_order > attack_order:
        return "opponent"
    return "opponent" if defense_type == "dodge" else "actor"


# ── Mixin ────────────────────────────────────────────────────────────

class CombatMixin:
    """Combat methods mixed into RoomStore."""

    # ── public API ──────────────────────────────────────────────────

    def start_combat(self, room_id: str, editor_id: str) -> dict:
        with self._lock:
            room = self._require_room(room_id)
            keeper = self._require_keeper(room, editor_id, "start combat")

            chars = room.get("characters", []) or []
            members = room.get("members", []) or []

            participants: list[dict] = []
            for char in chars:
                if char.get("active") is False:
                    continue
                character_id = char["id"]
                owner_id = char.get("ownerId")
                is_npc = not owner_id or char.get("isNpc") or False

                controller_member_id: str | None = None
                if is_npc:
                    controller_member_id = keeper["id"]
                else:
                    for m in members:
                        if m["id"] == owner_id:
                            controller_member_id = m["id"]
                            break
                    if controller_member_id is None:
                        controller_member_id = keeper["id"]

                hp_cur, hp_max = _get_hp(char)
                db, build = _get_db_and_build(char)
                # 恢复角色卡上持久化的伤情字段（combatStatus / dyingSinceRound
                # / majorWound），以便在已有战斗状态被重建时仍然能看到之前轮次
                # 产生的 dying / unconscious / dead / 重伤标志。
                c_status = char.get("status", {}) or {}
                persisted_status_raw = c_status.get("combatStatus") or "active"
                if persisted_status_raw == "major_wound":
                    # Back-compat: old code wrote "major_wound" into combatStatus
                    # before we split major-wound into a separate flag.
                    persisted_status = "active"
                    persisted_major_wound = True
                else:
                    persisted_status = persisted_status_raw
                    persisted_major_wound = bool(c_status.get("majorWound"))
                persisted_dying_round = c_status.get("dyingSinceRound")
                p = {
                    "characterId": character_id,
                    "controllerMemberId": controller_member_id,
                    "displayName": (char.get("basic", {}) or {}).get("name")
                                    or f"角色-{character_id[:6]}",
                    "dex": _get_attribute(char, "DEX"),
                    "hp": hp_cur,
                    "hpMax": hp_max,
                    "armor": _get_armor(char),
                    "db": db,
                    "build": build,
                    "status": persisted_status,
                    "majorWound": persisted_major_wound,
                    "hasActedThisRound": False,
                }
                if persisted_dying_round is not None:
                    p["dyingSinceRound"] = int(persisted_dying_round)
                participants.append(p)

            participants.sort(key=lambda p: p["dex"], reverse=True)

            combat_state = {
                "active": True,
                "roundNumber": 1,
                "phase": "declaration",
                "participants": participants,
                "intents": [],
                "defenses": [],
                "logs": [],
                "currentIntentIndex": 0,
                "createdAt": _now_iso(),
            }
            room["combatState"] = combat_state

            names = ", ".join(p["displayName"] for p in participants) or "(无参与者)"
            self._add_system_message(
                room,
                f"⚔️ {keeper['displayName']} 开启战斗。参与者：{names}。Round 1 - 宣告阶段。"
            )
            self._save()
            return deepcopy(combat_state)

    def get_combat_state(self, room_id: str) -> dict | None:
        with self._lock:
            room = self._require_room(room_id)
            cs = room.get("combatState")
            return deepcopy(cs) if cs else None

    def declare_combat_intents(
        self,
        room_id: str,
        editor_id: str,
        declarations: list[dict],
    ) -> dict:
        """Declare intents. Merges by characterId; never overwrites
        declarations from another controller unless the caller is keeper.
        """
        with self._lock:
            room = self._require_room(room_id)
            cs = room.get("combatState")
            if not cs or not cs.get("active"):
                raise ValueError("没有进行中的战斗")
            if cs["phase"] != "declaration":
                raise ValueError("当前不在宣告阶段")

            editor_member = self._find_member(room, editor_id)
            editor_role = editor_member.get("role")
            if editor_role == "spectator":
                raise PermissionError("spectator 不参与战斗")
            is_keeper = editor_role == "keeper"

            participants_by_id = {p["characterId"]: p for p in cs["participants"]}

            # validate every declaration is permitted (controller match or keeper)
            for decl in declarations:
                char_id = decl.get("characterId")
                if not char_id:
                    raise ValueError("缺少 characterId")
                if char_id not in participants_by_id:
                    raise ValueError(f"参与者 {char_id} 不在战斗中")
                participant = participants_by_id[char_id]
                if participant["status"] in ("unconscious", "dying", "dead"):
                    raise ValueError(f"{participant['displayName']} 无法行动")
                if not is_keeper and participant["controllerMemberId"] != editor_id:
                    raise PermissionError(
                        f"无法替 {participant['displayName']} 声明行动"
                    )
                action_type = decl.get("actionType") or "skip"
                if action_type not in ("melee_attack", "melee_maneuver", "skip"):
                    raise ValueError(f"未知的 actionType: {action_type}")
                targets = decl.get("targetCharacterIds") or []
                if action_type != "skip" and len(targets) != 1:
                    raise ValueError("近战攻击必须声明一个目标")
                for target_id in targets:
                    if target_id not in participants_by_id:
                        raise ValueError(f"目标 {target_id} 不在战斗中")
                    if target_id == char_id:
                        raise ValueError("不能以自己为目标")

            # Build the new intents list: keep previous declarations from
            # participants NOT touched by this editor; overwrite with new
            # declarations for participants this editor controls.
            existing_intents = {it["attackerCharacterId"]: it for it in cs["intents"]}
            for decl in declarations:
                char_id = decl["characterId"]
                action_type = decl["actionType"] or "skip"
                targets = decl.get("targetCharacterIds") or []
                existing_intents[char_id] = {
                    "intentId": uuid.uuid4().hex[:12],
                    "attackerCharacterId": char_id,
                    "actionType": action_type,
                    "weaponIndex": decl.get("weaponIndex"),
                    "targetCharacterIds": targets,
                    "resolved": False,
                }
            cs["intents"] = list(existing_intents.values())

            # Defense entries cannot exist prior to resolution phase here
            # (kept cleared until declaration is committed).
            self._save()
            return deepcopy(cs)

    def declare_combat_defenses(
        self,
        room_id: str,
        editor_id: str,
        defenses: list[dict],
    ) -> dict:
        """Accept defensive reactions after intents are declared.

        Stored per (intentId, defenderCharacterId). Only the keeper or
        the controller of defenderCharacterId may submit a defense for that
        defender. A defense_type of "none" is valid (no reaction).
        Only callable during the resolution phase — KP must lock the round
        via `lock_combat_intents` before any defense submission.
        """
        with self._lock:
            room = self._require_room(room_id)
            cs = room.get("combatState")
            if not cs or not cs.get("active"):
                raise ValueError("没有进行中的战斗")
            if cs["phase"] != "resolution":
                raise ValueError(
                    "防守阶段尚未开始：请 KP 先锁定本轮声明"
                )

            editor_member = self._find_member(room, editor_id)
            editor_role = editor_member.get("role")
            if editor_role == "spectator":
                raise PermissionError("spectator 不参与战斗")
            is_keeper = editor_role == "keeper"

            intents_by_id = {it["intentId"]: it for it in cs["intents"]}
            participants_by_id = {p["characterId"]: p for p in cs["participants"]}

            # Validate + upsert per (intentId, defenderCharacterId)
            existing = {(d["intentId"], d["defenderCharacterId"]): d
                        for d in cs.get("defenses", [])}
            for def_entry in defenses:
                intent_id = def_entry.get("intentId")
                defender_id = def_entry.get("defenderCharacterId")
                if not intent_id or not defender_id:
                    raise ValueError("防御声明必须包含 intentId 与 defenderCharacterId")
                intent = intents_by_id.get(intent_id)
                if not intent:
                    raise ValueError(f"未找到意图 {intent_id}")
                if defender_id not in intent.get("targetCharacterIds", []):
                    raise ValueError(
                        f"{defender_id} 不是意图 {intent_id} 的目标"
                    )
                defender = participants_by_id.get(defender_id)
                if not defender:
                    raise ValueError(f"未找到参与者 {defender_id}")
                if not is_keeper and defender["controllerMemberId"] != editor_id:
                    raise PermissionError(
                        f"无法替 {defender['displayName']} 选择防御"
                    )
                dtype = def_entry.get("defenseType") or "none"
                if dtype not in ("dodge", "fight_back", "maneuver", "none"):
                    raise ValueError(f"未知的 defenseType: {dtype}")
                key = (intent_id, defender_id)
                existing[key] = {
                    "intentId": intent_id,
                    "defenderCharacterId": defender_id,
                    "defenseType": dtype,
                    "weaponIndex": def_entry.get("weaponIndex"),
                    "submittedBy": editor_id,
                }
            cs["defenses"] = list(existing.values())
            self._save()
            return deepcopy(cs)

    def lock_combat_intents(self, room_id: str, editor_id: str) -> dict:
        """KP-only: move combat from declaration to resolution phase.

        This is the single gate that opens up defense submission and
        `resolve_all_combat` to the UI. A round without any declared intents
        can still be locked (nothing to resolve).
        """
        with self._lock:
            room = self._require_room(room_id)
            cs = room.get("combatState")
            if not cs or not cs.get("active"):
                raise ValueError("没有进行中的战斗")
            self._require_keeper(room, editor_id, "lock combat intents")
            if cs["phase"] != "declaration":
                raise ValueError("当前不在声明阶段")
            cs["phase"] = "resolution"
            self._add_system_message(
                room,
                f"⚔️ Round {cs['roundNumber']}：KP 已锁定声明，进入防守/结算阶段。"
            )
            self._save()
            return deepcopy(cs)

    def resolve_all_combat(self, room_id: str, editor_id: str) -> dict:
        """Resolve all declared intents in order. Keeper only.

        Intents are sorted by the attacker's DEX (descending). For each
        (attacker, defender) pair a defense is looked up: if not present
        it defaults to "none". When a defender already used a reaction
        against a previous attacker this round, every subsequent attacker
        targeting them gets +1 bonus die ("寡不敌众").

        Damage rules:
        - normal hit: roll(weapon) + DB (integers for known positive/
          zero values, else a d6-style roll).
        - extreme success, non-impale weapon: max(weapon) + DB (no
          extra roll).
        - impale on impaling weapon (critical or extreme success):
          max(weapon) + max(DB) + another rolled weapon damage.
        - armor reduces damage after bonuses are applied.
        Status transitions see `_apply_damage` below.
        """
        from app.modules.dice.roller import roll_dice

        with self._lock:
            room = self._require_room(room_id)
            cs = room.get("combatState")
            if not cs or not cs.get("active"):
                raise ValueError("没有进行中的战斗")

            self._require_keeper(room, editor_id, "resolve combat")

            if cs["phase"] != "resolution":
                raise ValueError(
                    "必须先由 KP 锁定声明进入结算阶段，才能执行结算"
                )

            participants_by_id = {p["characterId"]: p for p in cs["participants"]}
            defenses_map = {(d["intentId"], d["defenderCharacterId"]): d
                            for d in cs.get("defenses", [])}

            def _attacker_dex(it: dict) -> int:
                p = participants_by_id.get(it.get("attackerCharacterId"))
                return (p or {}).get("dex", 0)

            # (Re)sort intents by attacker DEX descending. We do NOT reset
            # `resolved` to False here — repeated `resolve_all_combat`
            # calls are idempotent: intents already marked resolved are
            # skipped, so defenders do not take damage a second time.
            ordered_intents = sorted(
                cs["intents"], key=_attacker_dex, reverse=True
            )

            # Per-defender reaction consumption: once a defender has used
            # any non-"none" reaction against an attacker, every subsequent
            # attacker targeting them gets +1 bonus die.
            defender_reacted: set[str] = set()

            # Attach a stable "order" to each intent so tests/logs can
            # inspect DEX ordering without relying on Python dict order.
            for idx, it in enumerate(ordered_intents):
                it["resolveOrder"] = idx
                # NOTE: we deliberately do NOT reset `resolved` here.

            new_logs: list[dict] = []

            for intent in ordered_intents:
                # Idempotent: never re-resolve an already resolved intent
                # (would double-roll / double-damage defenders).
                if intent.get("resolved"):
                    continue
                if intent["actionType"] == "skip":
                    intent["resolved"] = True
                    continue
                attacker = participants_by_id[intent["attackerCharacterId"]]
                if attacker is None:
                    intent["resolved"] = True
                    continue
                if attacker["status"] in ("unconscious", "dying", "dead"):
                    intent["resolved"] = True
                    continue

                attacker_char = self._find_character(
                    room, intent["attackerCharacterId"]
                )
                weapon = _get_weapon(attacker_char, intent.get("weaponIndex"))
                attack_skill = _get_weapon_skill_value(attacker_char, weapon)

                target_ids = intent.get("targetCharacterIds") or []
                for target_id in target_ids:
                    target = participants_by_id.get(target_id)
                    if target is None:
                        continue
                    if target["status"] in ("unconscious", "dying", "dead"):
                        continue

                    # Outnumber bonus: after the defender has used any
                    # reaction earlier this round, give +1 bonus die to
                    # subsequent attackers targeting that defender.
                    bonus_penalty = 1 if target_id in defender_reacted else 0

                    # Maneuver build penalty
                    if intent["actionType"] == "melee_maneuver":
                        build_diff = attacker["build"] - target["build"]
                        if build_diff <= -3:
                            self._add_combat_log(
                                cs, intent, attacker, target,
                                None, None, "maneuver",
                                damage_rolled=None, armor_used=None,
                                damage_after_armor=None,
                                impale=False, major_wound=False,
                                status_changed=None,
                                text=(
                                    f"{attacker['displayName']} 的 Build 太低，"
                                    f"无法对 {target['displayName']} 使用战技。"
                                ),
                                new_logs=new_logs,
                            )
                            continue
                        if build_diff < 0:
                            bonus_penalty += build_diff  # negative = penalty

                    defense = defenses_map.get((intent["intentId"], target_id))
                    target_char = self._find_character(room, target_id)
                    defense_type = (
                        defense["defenseType"] if defense else "none"
                    )
                    defense_weapon_idx = (
                        defense.get("weaponIndex") if defense else None
                    )

                    # Mark reaction as used — any non-"none" defense on
                    # this specific attacker is considered a reaction.
                    if defense_type in ("dodge", "fight_back", "maneuver"):
                        defender_reacted.add(target_id)

                    is_hit: bool = False
                    attack_roll = roll_dice(
                        "1d100", target_value=attack_skill,
                        bonus_penalty=bonus_penalty,
                    )
                    attack_ok = _roll_succeeded(attack_roll)
                    attack_success_level = attack_roll.get("successLevel")
                    log_defense_roll: dict | None = None
                    counter_dmg_target: int = 0
                    is_impale = False
                    damage_rolled: int | None = None
                    damage_after: int | None = None
                    major_w = False
                    status_changed: dict | None = None
                    log_text: str = ""

                    if defense_type in ("dodge", "fight_back", "maneuver"):
                        if defense_type == "dodge":
                            defense_skill = _get_dodge_value(target_char)
                        elif defense_type == "fight_back":
                            def_weapon = _get_weapon(
                                target_char, defense_weapon_idx
                            )
                            defense_skill = _get_weapon_skill_value(
                                target_char, def_weapon
                            )
                        else:  # maneuver
                            defense_skill = _get_maneuver_resist(target_char)

                        defense_roll = roll_dice(
                            "1d100", target_value=defense_skill
                        )
                        log_defense_roll = defense_roll
                        defense_ok = _roll_succeeded(defense_roll)

                        if not attack_ok and not defense_ok:
                            # Both fail — nothing happens.
                            log_text = (
                                f"{attacker['displayName']} 与 "
                                f"{target['displayName']} 均未命中（双失败）。"
                            )
                        else:
                            winner = _combat_opposed_winner(
                                attack_roll,
                                defense_roll,
                                defense_type,
                            )
                            if winner == "actor":
                                if intent["actionType"] == "melee_maneuver":
                                    log_text = (
                                        f"{attacker['displayName']} 战技成功，"
                                        f"压制 {target['displayName']}！"
                                    )
                                else:
                                    is_hit = True
                            elif winner == "opponent" and defense_type == "fight_back":
                                # Defender counter-attack succeeds
                                def_weapon = _get_weapon(
                                    target_char, defense_weapon_idx
                                )
                                counter_base_expr = (
                                    _get_weapon_damage_expr(def_weapon)
                                )
                                counter_roll = roll_dice(counter_base_expr)
                                counter_db_txt = target["db"]
                                counter_db: int
                                if counter_db_txt in ("0", "-1", "-2"):
                                    counter_db = int(counter_db_txt)
                                elif counter_db_txt and counter_db_txt.lstrip('-').isdigit():
                                    counter_db = int(counter_db_txt)
                                else:
                                    counter_db = (
                                        roll_dice(counter_db_txt)["total"]
                                        if counter_db_txt else 0
                                    )
                                counter_raw = counter_roll["total"] + counter_db
                                counter_final = max(0, counter_raw - attacker["armor"])
                                counter_dmg_target = counter_final
                                # apply to attacker
                                status_changed = self._apply_damage(
                                    room, cs, attacker, counter_final,
                                    intent, weapon_kind="counter",
                                )
                                log_text = (
                                    f"{target['displayName']} 反击成功！对 "
                                    f"{attacker['displayName']} 造成 {counter_final} 点伤害"
                                )
                            else:
                                # dodge/maneuver defender win
                                log_text = (
                                    f"{target['displayName']} 的 {defense_type} 成功"
                                    f" 防御住了 {attacker['displayName']}"
                                )
                    else:
                        # No reaction: straight hit check
                        if attack_ok:
                            is_hit = True
                        else:
                            log_text = (
                                f"{attacker['displayName']} 攻击 "
                                f"{target['displayName']} 未命中 "
                                f"({attack_roll['total']}/{attack_skill})"
                            )

                    if is_hit and intent["actionType"] == "melee_attack":
                        is_imp = _is_impaling_weapon(weapon)
                        weapon_expr = _get_weapon_damage_expr(weapon)
                        db_txt = attacker["db"]
                        if db_txt in ("0", "-1", "-2"):
                            db_val = int(db_txt)
                        elif db_txt and db_txt.lstrip('-').isdigit():
                            db_val = int(db_txt)
                        else:
                            db_val = (
                                roll_dice(db_txt)["total"] if db_txt else 0
                            )
                        is_extreme = attack_success_level in (
                            "extreme", "critical"
                        )
                        if is_extreme and is_imp:
                            # Impale branch
                            extra_roll = roll_dice(weapon_expr)["total"]
                            max_weapon = _max_damage(weapon_expr)
                            if db_txt in ("0", "-1", "-2"):
                                max_db = int(db_txt)
                            else:
                                max_db = _max_damage(db_txt) if db_txt else 0
                            raw_dmg = max_weapon + max_db + extra_roll
                            is_impale = True
                        elif is_extreme:
                            # Non-impale extreme = max weapon + DB
                            raw_dmg = _max_damage(weapon_expr) + db_val
                        else:
                            base_roll = roll_dice(weapon_expr)
                            raw_dmg = base_roll["total"] + db_val
                        damage_rolled = raw_dmg
                        damage_after = max(0, raw_dmg - target["armor"])
                        major_w = damage_after > 0 and damage_after * 2 >= target["hpMax"]
                        status_changed = self._apply_damage(
                            room, cs, target, damage_after, intent,
                            weapon_kind="attack",
                        )
                        log_text = (
                            f"{attacker['displayName']} 对 {target['displayName']} "
                            f"造成 {damage_after} 点伤害 "
                            f"(出目 {attack_roll['total']}/{attack_skill}"
                            f"{'; 贯穿!' if is_impale else ''})"
                        )
                    elif is_hit and intent["actionType"] == "melee_maneuver":
                        pass

                    self._add_combat_log(
                        cs, intent, attacker, target,
                        attack_roll, log_defense_roll, defense_type,
                        damage_rolled=damage_rolled,
                        armor_used=target["armor"],
                        damage_after_armor=damage_after,
                        impale=is_impale,
                        major_wound=major_w,
                        status_changed=status_changed,
                        text=log_text or "无变化",
                        new_logs=new_logs,
                    )

                intent["resolved"] = True
                attacker["hasActedThisRound"] = True

            cs["logs"] = new_logs + (cs.get("logs") or [])
            # Phase stays "resolution" — KP uses next_combat_round to
            # return to declaration phase for the next round.
            self._save()
            return deepcopy(cs)

    def next_combat_round(self, room_id: str, editor_id: str) -> dict:
        from app.modules.dice.roller import roll_dice

        with self._lock:
            room = self._require_room(room_id)
            cs = room.get("combatState")
            if not cs or not cs.get("active"):
                raise ValueError("没有进行中的战斗")
            self._require_keeper(room, editor_id, "advance combat round")

            # --- "下一轮结束" 的标准流程：先清声明 / 防御，再递增轮次 ---
            cs["phase"] = "declaration"
            cs["intents"] = []
            cs["defenses"] = []
            cs["currentIntentIndex"] = 0
            for p in cs.get("participants", []):
                p["hasActedThisRound"] = False
            cs["roundNumber"] = int(cs.get("roundNumber", 0)) + 1
            current_round = cs["roundNumber"]

            # 濒死角色的首次 CON 检查发生在"完成 N+1 轮后进入
            # N+2 轮时"（即倒下后至少完整度过一轮）。这里的
            # current_round 是刚刚递增之后的新轮次编号，所以我们
            #要求 dyingSinceRound < current_round - 1，也就是
            # dyingSinceRound <= current_round - 2。
            round_msgs: list[str] = []
            chars_by_id = {c["id"]: c for c in room.get("characters", [])}
            for p in cs.get("participants", []):
                if p["status"] != "dying":
                    continue
                dying_since = int(p.get("dyingSinceRound") or 0)
                # 跳过 dying 后还未满一轮的成员（即进入 N+1 轮时不检查）。
                if dying_since >= current_round - 1:
                    continue
                target_char = self._find_character(room, p["characterId"])
                con = _get_attribute(target_char, "CON")
                con_roll = roll_dice("1d100", target_value=con)
                if con_roll["total"] > con:
                    p["status"] = "dead"
                    p.pop("dyingSinceRound", None)
                    round_msgs.append(f"{p['displayName']} 濒死 CON 失败，死亡。")
                else:
                    round_msgs.append(f"{p['displayName']} 濒死 CON 通过，仍存一息。")

                # 同步 participant → 角色卡，确保下次进入战斗 / 重建 participants
                # 时仍能看到最新状态，不会因重初始化而把 dying 状态丢掉。
                c = chars_by_id.get(p["characterId"])
                if c is not None:
                    c_status = c.setdefault("status", {})
                    c_status["hp"] = p["hp"]
                    c_status["combatStatus"] = p["status"]
                    if p.get("majorWound"):
                        c_status["majorWound"] = True
                    else:
                        c_status.pop("majorWound", None)
                    if p.get("dyingSinceRound") is not None:
                        c_status["dyingSinceRound"] = p["dyingSinceRound"]
                    else:
                        c_status.pop("dyingSinceRound", None)

            self._add_system_message(
                room,
                f"⚔️ Round {cs['roundNumber']} - 宣告阶段。"
                + (f" {' '.join(round_msgs)}" if round_msgs else "")
            )
            self._save()
            return deepcopy(cs)

    def end_combat(self, room_id: str, editor_id: str) -> dict:
        with self._lock:
            room = self._require_room(room_id)
            editor = self._require_keeper(room, editor_id, "end combat")
            if "combatState" in room:
                del room["combatState"]
            self._add_system_message(room, f"{editor['displayName']} 结束了战斗轮次。")
            self._save()
            return deepcopy(room)

    # ── internal helpers ──────────────────────────────────────────────

    def _apply_damage(
        self,
        room: dict,
        cs: dict,
        target: dict,
        damage: int,
        intent: dict | None = None,
        *,
        weapon_kind: str = "attack",
    ) -> dict | None:
        """Apply `damage` HP loss to `target` and transition status.

        Returns status change dict if a transition happened, else None.

        HP = 0 always knocks the character unconscious unless they are
        already dying (in which case the additional damage kills them) or
        are already dead.

        A single hit dealing damage >= hpMax kills the character outright.

        A hit causing a major wound (>= hpMax/2) and leaving HP > 0 rolls
        a CON check: failing moves to unconscious; passing stays in the
        active → major_wound status path.
        """
        if damage <= 0:
            return None
        prev_status = target["status"]
        prev_hp = target["hp"]
        target["hp"] = max(0, target["hp"] - damage)
        hp_max = target["hpMax"]
        hp_after = target["hp"]
        new_status: str | None = None

        # Major-wound flag — kept separate from conscious status so repeated
        # major wounds still trigger a CON check (the original bug).
        is_major = (damage * 2 >= hp_max) and hp_max > 0
        # CoC 7e: a single hit dealing damage >= the character's max HP
        # is instantly lethal (massive damage).
        is_instant_death = damage >= hp_max

        from app.modules.dice.roller import roll_dice
        target_char = self._find_character(room, target["characterId"])
        con = _get_attribute(target_char, "CON")

        can_act = prev_status not in ("unconscious", "dying", "dead")

        if is_instant_death:
            new_status = "dead"
            target["majorWound"] = True
            self._add_system_message(
                room,
                f"💀 {target['displayName']} 受到 {damage} 点伤害（≥ 最大 HP "
                f"{hp_max}），立即死亡。"
            )
        elif hp_after == 0:
            if prev_status == "dying":
                # Already dying at 0 HP; further damage does not auto-kill.
                pass
            elif prev_status == "unconscious":
                # HP = 0 while already unconscious → dying.
                new_status = "dying"
                target["majorWound"] = True
                self._add_system_message(
                    room,
                    f"😵 {target['displayName']} 昏迷时 HP 降至 0，进入濒死。"
                )
            else:
                # active / was previously major-wounded at HP > 0 before; now 0.
                # If this is a major wound → dying; otherwise unconscious.
                if is_major:
                    new_status = "dying"
                    target["majorWound"] = True
                    self._add_system_message(
                        room,
                        f"😵 {target['displayName']} 受到重创（{damage} 点），"
                        f"HP 归零且失去意识，进入濒死状态。"
                    )
                else:
                    new_status = "unconscious"
                    self._add_system_message(
                        room,
                        f"😵 {target['displayName']} HP 归零，失去意识。"
                    )
        elif is_major and can_act:
            # Major wound while HP still > 0 and the character can still act →
            # CON check (fails → unconscious; passes → still active but
            # marked major-wound).
            con_roll = roll_dice("1d100", target_value=con)
            if con_roll["total"] > con:
                new_status = "unconscious"
                target["majorWound"] = True
                self._add_system_message(
                    room,
                    f"💥 {target['displayName']} 受到重伤（{damage}/{hp_max}），"
                    f"CON 检定 {con_roll['total']}/{con} 失败，昏迷。"
                )
            else:
                target["majorWound"] = True
                self._add_system_message(
                    room,
                    f"💥 {target['displayName']} 受到重伤（{damage}/{hp_max}），"
                    f"CON 通过（{con_roll['total']}/{con}），保持清醒。"
                )
        elif is_major:
            # Major wound on a character that cannot act → mark major wound
            # HP dropped them to dying on the floor (already non-0 from a non-major wound).
            target["majorWound"] = True
        # Counter-attack or minor damage do not change status.

        status_changed = None
        if new_status is not None and new_status != prev_status:
            target["status"] = new_status
            status_changed = {"from": prev_status, "to": new_status}
            # Remember the combat round the character entered the dying state
            # so we can defer CON checks until the *next* round.
            if new_status == "dying":
                target["dyingSinceRound"] = cs.get("roundNumber", 0)
            elif "dyingSinceRound" in target and new_status in ("dead", "active"):
                target.pop("dyingSinceRound", None)
        # Mirror participant hp / status / dyingSinceRound onto the backing
        # character card so they survive round transitions.
        target_char = self._find_character(
            room, target["characterId"]
        ) if cs else None
        if target_char is not None:
            c_status = target_char.setdefault("status", {})
            c_status["hp"] = target["hp"]
            if target.get("status") is not None:
                c_status["combatStatus"] = target["status"]
            if target.get("majorWound"):
                c_status["majorWound"] = True
            else:
                c_status.pop("majorWound", None)
            if target.get("dyingSinceRound") is not None:
                c_status["dyingSinceRound"] = target["dyingSinceRound"]
            else:
                c_status.pop("dyingSinceRound", None)
        return status_changed

    def _add_combat_log(
        self,
        cs: dict,
        intent: dict,
        attacker: dict,
        defender: dict,
        attack_roll: dict | None,
        defense_roll: dict | None,
        defense_type: str,
        *,
        damage_rolled: int | None,
        armor_used: int | None,
        damage_after_armor: int | None,
        impale: bool,
        major_wound: bool,
        status_changed: dict | None,
        text: str,
        new_logs: list[dict],
    ) -> None:
        entry = {
            "roundNumber": cs["roundNumber"],
            "attacker": {
                "characterId": attacker["characterId"],
                "displayName": attacker["displayName"],
                "roll": self._roll_to_public(attack_roll) if attack_roll else None,
                "actionType": intent.get("actionType"),
            },
            "defender": {
                "characterId": defender["characterId"],
                "displayName": defender["displayName"],
                "defenseType": defense_type,
                "roll": self._roll_to_public(defense_roll) if defense_roll else None,
            },
            "damageRolled": damage_rolled,
            "damageAfterArmor": damage_after_armor,
            "armorUsed": armor_used,
            "impale": impale,
            "majorWound": major_wound,
            "statusChanged": status_changed,
            "resultText": text,
            "timestamp": _now_iso(),
        }
        new_logs.append(entry)

    @staticmethod
    def _roll_to_public(roll: dict | None) -> dict | None:
        if not roll:
            return None
        return {
            "expression": roll.get("expression", "1d100"),
            "total": roll.get("total", 0),
            "targetValue": roll.get("targetValue"),
            "bonusPenalty": roll.get("bonusPenalty", 0),
            "successLevel": roll.get("successLevel"),
            "successLabel": roll.get("successLabel"),
        }
