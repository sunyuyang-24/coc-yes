"""COC 7e advanced rules endpoints (opposed rolls, healing, wounds, insanity, pushing, structured checks, SAN checks)."""

from fastapi import APIRouter, Form, HTTPException

from app.modules.dice.roller import (
    roll_dice, opposed_check, pushing_check,
    first_aid_check, medicine_check, major_wound_check,
    insanity_check, weapon_malfunction_check,
)
from app.modules.rooms.deps import store, manager
from app.modules.rooms.schemas import CheckRequest, SanCheckRequest

router = APIRouter()


# ── COC 7e Advanced Rules ──

@router.post("/rooms/{room_id}/coc/opposed")
async def opposed_roll(room_id: str, expression: str = Form("1d100"), target: str = Form("50"),
                       opponentExpression: str = Form("1d100"), opponentTarget: str = Form("50"),
                       actorTotal: str = Form(""), opponentTotal: str = Form(""),
                       defenderWinsTie: str = Form("false")) -> dict:
    try:
        target_int = int(target)
        opp_target_int = int(opponentTarget)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid numeric value for target")

    if actorTotal and opponentTotal:
        try:
            actor = {"total": int(actorTotal), "targetValue": target_int, "breakdown": []}
            opponent = {"total": int(opponentTotal), "targetValue": opp_target_int, "breakdown": []}
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid numeric value for pre-rolled total")
    else:
        actor = roll_dice(expression, target_value=target_int)
        opponent = roll_dice(opponentExpression, target_value=opp_target_int)

    dw_tie = defenderWinsTie.lower() == "true"
    result = opposed_check(actor["total"], target_int, opponent["total"], opp_target_int, defender_wins_tie=dw_tie)
    return {"actor": actor, "opponent": opponent, "result": result}


@router.post("/rooms/{room_id}/coc/heal")
async def heal_check(room_id: str, hpCurrent: str = Form("0"), hpMax: str = Form("10"),
                     healType: str = Form("first_aid")) -> dict:
    try:
        chp, mhp = int(hpCurrent), int(hpMax)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid numeric value for HP")
    if healType == "medicine":
        return medicine_check(chp, mhp)
    return first_aid_check(chp, mhp)


@router.post("/rooms/{room_id}/coc/firstaid")
async def firstaid_alias(room_id: str, hpCurrent: str = Form("0"), hpMax: str = Form("10")) -> dict:
    try:
        return first_aid_check(int(hpCurrent), int(hpMax))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid numeric value for HP")


@router.post("/rooms/{room_id}/coc/majorwound")
async def majorwound_alias(room_id: str, damage: str = Form("0"), hpMax: str = Form("10")) -> dict:
    try:
        return major_wound_check(int(damage), int(hpMax))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid numeric value for damage or HP")


@router.post("/rooms/{room_id}/coc/wound")
async def wound_check(room_id: str, damage: str = Form("0"), hpMax: str = Form("10")) -> dict:
    try:
        damage_int = int(damage)
        hp_max_int = int(hpMax)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid numeric value for damage or HP")
    return major_wound_check(damage_int, hp_max_int)


@router.post("/rooms/{room_id}/coc/insanity")
async def insanity_roll(room_id: str, sanLoss: str = Form("0"), currentSAN: str = Form("50"),
                        maxSAN: str = Form("50")) -> dict:
    try:
        san_loss_int = int(sanLoss)
        cur_san_int = int(currentSAN)
        max_san_int = int(maxSAN)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid numeric value for SAN")
    return insanity_check(san_loss_int, cur_san_int, max_san_int)


@router.post("/rooms/{room_id}/coc/malfunction")
async def malf_check(room_id: str, total: str = Form("0"), malfValue: str = Form("96")) -> dict:
    try:
        return weapon_malfunction_check(int(total), int(malfValue))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid numeric value for malfunction check")


@router.post("/rooms/{room_id}/coc/pushing")
async def pushing_roll(room_id: str, total: str = Form("0"), target: str = Form("50"),
                       isPushed: str = Form("false")) -> dict:
    try:
        return pushing_check(int(total), int(target), isPushed.lower() == "true")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid numeric value for pushing check")


# ── Structured Skill/Attribute Check ──

_SKILL_ALIASES: dict[str, str] = {
    "dodge": "闪避", "library use": "图书馆使用", "spot hidden": "侦查",
    "listen": "聆听", "psychology": "心理学", "stealth": "潜行",
    "first aid": "急救", "medicine": "医学", " occult": "神秘学",
    "history": "历史", "archaeology": "考古学", "law": "法律",
    "fast talk": "话术", "persuade": "说服", "intimidate": "恐吓",
    "charm": "魅惑", "climb": "攀爬", "swim": "游泳", "jump": "跳跃",
    "drive auto": "汽车驾驶", "pilot": "驾驶", "ride": "骑术",
    "fighting": "格斗", "brawl": "格斗(斗殴)", "firearms": "射击",
    "handgun": "射击(手枪)", "rifle": "射击(步枪)", "shotgun": "射击(霰弹枪)",
}


@router.post("/rooms/{room_id}/rolls/check")
async def structured_check(room_id: str, payload: CheckRequest) -> dict:
    try:
        room = store._require_room(room_id)
        character = store._find_character(room, payload.character_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room or character not found") from error

    target_value = 50
    label = ""
    if payload.skill_name:
        lookup = payload.skill_name.strip()
        for sk in character.get("skills", []):
            sk_name = (sk.get("name") or "").strip()
            if sk_name == lookup or sk_name.lower() == lookup.lower():
                val = sk.get("value") or 50
                if payload.difficulty == "hard":
                    target_value = val // 2
                elif payload.difficulty == "extreme":
                    target_value = val // 5
                else:
                    target_value = val
                label = f"{character.get('basic', {}).get('name', '??')} | {sk_name}"
                break
            if _SKILL_ALIASES.get(lookup.lower()) == sk_name:
                val = sk.get("value") or 50
                if payload.difficulty == "hard":
                    target_value = val // 2
                elif payload.difficulty == "extreme":
                    target_value = val // 5
                else:
                    target_value = val
                label = f"{character.get('basic', {}).get('name', '??')} | {sk_name}"
                break
    elif payload.attribute_key:
        for attr in character.get("attributes", []):
            if attr.get("key") == payload.attribute_key:
                val = attr.get("value") or 50
                if payload.difficulty == "hard":
                    target_value = val // 2
                elif payload.difficulty == "extreme":
                    target_value = val // 5
                else:
                    target_value = val
                label = f"{character.get('basic', {}).get('name', '??')} | {attr.get('label', payload.attribute_key)}"
                break

    roll = roll_dice("1d100", target_value=target_value, label=label, hidden=payload.hidden)
    roll_record = store.add_dice_roll(room_id, character.get("ownerId", ""), roll)
    room = store.get_room(room_id)
    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"roll": roll_record}


@router.post("/rooms/{room_id}/rolls/san-check")
async def san_check(room_id: str, payload: SanCheckRequest) -> dict:
    try:
        room = store._require_room(room_id)
        character = store._find_character(room, payload.character_id)
        roller_id = character.get("ownerId", "")
        if not roller_id:
            raise HTTPException(status_code=400, detail="Character has no owner")
        result = store.san_check_roll(
            room_id, roller_id, payload.character_id,
            payload.success_loss, payload.failure_loss, payload.hidden,
        )
        room = store.get_room(room_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"result": result}
