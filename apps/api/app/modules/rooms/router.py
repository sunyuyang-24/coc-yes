from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.modules.dice.roller import roll_dice
from app.modules.dice.schemas import RollDiceRequest
from app.modules.rooms.connection_manager import RoomConnectionManager
from app.modules.rooms.schemas import CreateRoomRequest, JoinRoomRequest, SendMessageRequest
from app.modules.rooms.store import RoomStore

router = APIRouter()
store = RoomStore(settings.data_dir / "rooms.json")
manager = RoomConnectionManager()


@router.post("/rooms")
async def create_room(payload: CreateRoomRequest) -> dict:
    room, member_id = store.create_room(payload.name, payload.keeper_name)
    return {
        "room": room,
        "currentMemberId": member_id,
    }


@router.post("/rooms/join")
async def join_room(payload: JoinRoomRequest) -> dict:
    try:
        room, member_id = store.join_room(payload.invite_code, payload.display_name)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Invite code not found") from error

    await manager.broadcast(room["id"], {"type": "room_update", "room": room})

    return {
        "room": room,
        "currentMemberId": member_id,
    }


@router.get("/rooms/{room_id}")
async def get_room(room_id: str) -> dict:
    try:
        return {"room": store.get_room(room_id)}
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room not found") from error


@router.post("/rooms/{room_id}/messages")
async def send_message(room_id: str, payload: SendMessageRequest) -> dict:
    try:
        message = store.add_message(room_id, payload.sender_id, payload.content)
        room = store.get_room(room_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room or member not found") from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room})

    return {"message": message}


@router.post("/rooms/{room_id}/rolls")
async def roll_in_room(room_id: str, payload: RollDiceRequest) -> dict:
    try:
        roll = roll_dice(
            payload.expression,
            target_value=payload.target_value,
            bonus_penalty=payload.bonus_penalty,
            label=payload.label,
        )
        roll_record = store.add_dice_roll(room_id, payload.roller_id, roll)
        room = store.get_room(room_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room or member not found") from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room})

    return {"roll": roll_record}


@router.websocket("/rooms/{room_id}/ws")
async def room_socket(websocket: WebSocket, room_id: str, member_id: str) -> None:
    try:
        room = store.set_member_online(room_id, member_id, True)
    except KeyError:
        await websocket.close(code=4404)
        return

    await manager.connect(room_id, websocket)
    await manager.broadcast(room_id, {"type": "room_update", "room": room})

    try:
        await websocket.send_json({"type": "room_state", "room": room})

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(room_id, websocket)

        try:
            room = store.set_member_online(room_id, member_id, False)
        except KeyError:
            return

        await manager.broadcast(room_id, {"type": "room_update", "room": room})
