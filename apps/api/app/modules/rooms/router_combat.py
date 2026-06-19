"""Combat endpoints for the CoC 7e round workflow."""

from fastapi import APIRouter, Form, HTTPException

from app.modules.rooms.deps import manager, store
from app.modules.rooms.schemas import (
    DeclareCombatDefensesRequest,
    DeclareCombatIntentsRequest,
    NextCombatRoundRequest,
    ResolveCombatRequest,
)

router = APIRouter()


async def _broadcast_room(room_id: str) -> dict:
    room = store.get_room(room_id)
    await manager.broadcast(
        room_id,
        {"type": "room_update", "room": room},
        store,
    )
    return room


def _to_http_error(error: Exception) -> HTTPException:
    if isinstance(error, PermissionError):
        return HTTPException(status_code=403, detail=str(error))
    if isinstance(error, KeyError):
        return HTTPException(status_code=404, detail=str(error))
    return HTTPException(status_code=400, detail=str(error))


@router.post("/rooms/{room_id}/combat/start")
async def start_combat(
    room_id: str,
    editor_id: str = Form(..., alias="editorId"),
) -> dict:
    try:
        combat_state = store.start_combat(room_id, editor_id)
        await _broadcast_room(room_id)
        return {"combatState": combat_state}
    except (KeyError, PermissionError, ValueError) as error:
        raise _to_http_error(error) from error


@router.get("/rooms/{room_id}/combat/state")
async def get_combat_state(room_id: str) -> dict:
    try:
        return {"combatState": store.get_combat_state(room_id)}
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room not found") from error


@router.post("/rooms/{room_id}/combat/declare")
async def declare_combat_intents(
    room_id: str,
    payload: DeclareCombatIntentsRequest,
) -> dict:
    try:
        combat_state = store.declare_combat_intents(
            room_id,
            payload.member_id,
            [declaration.model_dump() for declaration in payload.declarations],
        )
        await _broadcast_room(room_id)
        return {"combatState": combat_state}
    except (KeyError, PermissionError, ValueError) as error:
        raise _to_http_error(error) from error


@router.post("/rooms/{room_id}/combat/lock")
async def lock_combat_intents(
    room_id: str,
    payload: ResolveCombatRequest,
) -> dict:
    try:
        combat_state = store.lock_combat_intents(room_id, payload.editor_id)
        await _broadcast_room(room_id)
        return {"combatState": combat_state}
    except (KeyError, PermissionError, ValueError) as error:
        raise _to_http_error(error) from error


@router.post("/rooms/{room_id}/combat/defense")
async def declare_combat_defenses(
    room_id: str,
    payload: DeclareCombatDefensesRequest,
) -> dict:
    try:
        combat_state = store.declare_combat_defenses(
            room_id,
            payload.member_id,
            [defense.model_dump() for defense in payload.defenses],
        )
        await _broadcast_room(room_id)
        return {"combatState": combat_state}
    except (KeyError, PermissionError, ValueError) as error:
        raise _to_http_error(error) from error


@router.post("/rooms/{room_id}/combat/resolve")
async def resolve_combat(
    room_id: str,
    payload: ResolveCombatRequest,
) -> dict:
    try:
        combat_state = store.resolve_all_combat(room_id, payload.editor_id)
        await _broadcast_room(room_id)
        return {"combatState": combat_state}
    except (KeyError, PermissionError, ValueError) as error:
        raise _to_http_error(error) from error


@router.post("/rooms/{room_id}/combat/next_round")
async def next_combat_round(
    room_id: str,
    payload: NextCombatRoundRequest,
) -> dict:
    try:
        combat_state = store.next_combat_round(room_id, payload.editor_id)
        await _broadcast_room(room_id)
        return {"combatState": combat_state}
    except (KeyError, PermissionError, ValueError) as error:
        raise _to_http_error(error) from error


@router.post("/rooms/{room_id}/combat/end")
async def end_combat(
    room_id: str,
    payload: ResolveCombatRequest,
) -> dict:
    try:
        room = store.end_combat(room_id, payload.editor_id)
        await _broadcast_room(room_id)
        return {"room": room}
    except (KeyError, PermissionError, ValueError) as error:
        raise _to_http_error(error) from error
