"""Combat endpoints for rooms."""

from fastapi import APIRouter, Form, HTTPException

from app.modules.rooms.schemas import CombatActionRequest
from app.modules.rooms.deps import store, manager

router = APIRouter()


@router.post("/rooms/{room_id}/combat/start")
async def start_combat(room_id: str, editor_id: str = Form(..., alias="editorId")) -> dict:
    try:
        combat_state = store.start_combat(room_id, editor_id)
        room = store.get_room(room_id)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room or member not found") from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"combatState": combat_state}


@router.get("/rooms/{room_id}/combat/state")
async def get_combat_state(room_id: str) -> dict:
    try:
        cs = store.get_combat_state(room_id)
        return {"combatState": cs}
    except KeyError:
        raise HTTPException(status_code=404, detail="Room not found")


@router.post("/rooms/{room_id}/combat/action")
async def combat_action(room_id: str, payload: CombatActionRequest) -> dict:
    try:
        cs = store.act_combat(
            room_id, payload.attacker_id, payload.weapon_index,
            payload.defender_id, payload.action_type, payload.hidden,
        )
        room = store.get_room(room_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"combatState": cs}


@router.post("/rooms/{room_id}/combat/act")
async def combat_act_alias(room_id: str, payload: CombatActionRequest) -> dict:
    """Alias for /combat/action."""
    return await combat_action(room_id, payload)


@router.post("/rooms/{room_id}/combat/end")
async def end_combat(room_id: str, editor_id: str = Form(..., alias="editorId")) -> dict:
    try:
        room = store.end_combat(room_id, editor_id)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room or member not found") from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"room": room}
