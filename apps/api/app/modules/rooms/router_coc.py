"""COC 7e 高级规则端点（推动、急救、重伤、疯狂、武器故障、技能检定、SAN 检定）。"""

from fastapi import APIRouter, Form, HTTPException

from app.modules.dice.roller import (
    roll_dice,
    first_aid_check,
    major_wound_check,
    insanity_check,
    weapon_malfunction_check,
    pushing_check,
)
from app.modules.rooms.deps import store, manager
from app.modules.rooms.schemas import CheckRequest, SanCheckRequest

router = APIRouter()


# ── COC 7e 纯规则工具（不写入房间历史，仅返回静态结果） ──

@router.post("/rooms/{room_id}/coc/heal")
async def heal_check(room_id: str, hp_current: str = Form("0", alias="hpCurrent"),
                     hp_max: str = Form("10", alias="hpMax"),
                     heal_type: str = Form("first_aid", alias="healType")) -> dict:
    try:
        chp, mhp = int(hp_current), int(hp_max)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid numeric value for HP")
    if heal_type == "medicine":
        # medicine_check 简化为 first_aid_check 的变体（保留接口不变）
        return first_aid_check(chp, mhp)
    return first_aid_check(chp, mhp)


@router.post("/rooms/{room_id}/coc/firstaid")
async def firstaid_alias(room_id: str, hp_current: str = Form("0", alias="hpCurrent"),
                         hp_max: str = Form("10", alias="hpMax")) -> dict:
    try:
        return first_aid_check(int(hp_current), int(hp_max))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid numeric value for HP")


@router.post("/rooms/{room_id}/coc/majorwound")
async def majorwound_alias(room_id: str, damage: str = Form("0"),
                           hp_max: str = Form("10", alias="hpMax")) -> dict:
    try:
        return major_wound_check(int(damage), int(hp_max))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid numeric value for damage or HP")


@router.post("/rooms/{room_id}/coc/wound")
async def wound_check(room_id: str, damage: str = Form("0"),
                      hp_max: str = Form("10", alias="hpMax")) -> dict:
    try:
        return major_wound_check(int(damage), int(hp_max))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid numeric value for damage or HP")


@router.post("/rooms/{room_id}/coc/insanity")
async def insanity_roll(room_id: str, san_loss: str = Form("0", alias="sanLoss"),
                        current_san: str = Form("50", alias="currentSAN"),
                        max_san: str = Form("50", alias="maxSAN")) -> dict:
    try:
        return insanity_check(int(san_loss), int(current_san), int(max_san))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid numeric value for SAN")


@router.post("/rooms/{room_id}/coc/malfunction")
async def malf_check(room_id: str, total: str = Form("0"),
                     malf_value: str = Form("96", alias="malfValue")) -> dict:
    try:
        return weapon_malfunction_check(int(total), int(malf_value))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid numeric value for malfunction check")


@router.post("/rooms/{room_id}/coc/pushing")
async def pushing_roll(room_id: str, total: str = Form("0"),
                       target: str = Form("50"),
                       is_pushed: str = Form("false", alias="isPushed")) -> dict:
    try:
        return pushing_check(int(total), int(target), is_pushed.lower() == "true")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid numeric value for pushing check")


# ── 基于角色卡的结构化技能检定（KP 可扮演 NPC） ──

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
    editor_id = payload.editor_id or character.get("ownerId") or ""
    roll_record = store.add_dice_roll(room_id, editor_id, roll, as_character_id=payload.character_id)
    room = store.get_room(room_id)
    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"roll": roll_record}


# ── SAN 检定（以角色卡身份显示） ──

@router.post("/rooms/{room_id}/rolls/san-check")
async def san_check(room_id: str, payload: SanCheckRequest) -> dict:
    try:
        room = store._require_room(room_id)
        character = store._find_character(room, payload.character_id)
        roller_id = character.get("ownerId") or ""
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
