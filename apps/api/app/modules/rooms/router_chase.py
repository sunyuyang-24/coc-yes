"""Chase endpoints for rooms."""

from fastapi import APIRouter, Form, HTTPException

from app.modules.rooms.deps import store, manager
from app.modules.rooms.schemas import ChaseActionRequest

router = APIRouter()


@router.post("/rooms/{room_id}/chase/start")
async def start_chase(room_id: str, editor_id: str = Form(..., alias="editorId")) -> dict:
    try:
        chase_state = store.start_chase(room_id, editor_id)
        room = store.get_room(room_id)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room or member not found") from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"chaseState": chase_state}


@router.get("/rooms/{room_id}/chase/state")
async def get_chase_state(room_id: str) -> dict:
    try:
        cs = store.get_chase_state(room_id)
        return {"chaseState": cs}
    except KeyError:
        raise HTTPException(status_code=404, detail="Room not found")


@router.post("/rooms/{room_id}/chase/action")
async def chase_action(room_id: str, payload: ChaseActionRequest) -> dict:
    try:
        cs = store.act_chase(
            room_id, payload.participant_id, payload.action_type,
            payload.weapon_index, payload.hidden,
        )
        room = store.get_room(room_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"chaseState": cs}


@router.post("/rooms/{room_id}/chase/end")
async def end_chase(room_id: str, editor_id: str = Form(..., alias="editorId")) -> dict:
    try:
        room = store.end_chase(room_id, editor_id)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room or member not found") from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"room": room}
