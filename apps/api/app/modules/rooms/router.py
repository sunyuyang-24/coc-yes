from fastapi import APIRouter, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from uuid import uuid4

from app.core.config import settings
from app.modules.characters.parser import parse_character_card
from app.modules.characters.schemas import UpdateCharacterRequest
from app.modules.dice.roller import (
    roll_dice, opposed_check, pushing_check,
    first_aid_check, medicine_check, major_wound_check,
    insanity_check, weapon_malfunction_check,
)
from app.modules.dice.schemas import RollDiceRequest
from app.modules.rooms.connection_manager import RoomConnectionManager
from app.modules.rooms.schemas import CreateRoomRequest, JoinRoomRequest, SendMessageRequest
from app.modules.rooms.store import RoomStore

router = APIRouter()
store = RoomStore(settings.data_dir / "rooms.json")
manager = RoomConnectionManager()


@router.post("/rooms")
async def create_room(payload: CreateRoomRequest) -> dict:
    room, member_id = store.create_room(payload.name, payload.keeper_name, payload.password)
    return {
        "room": room,
        "currentMemberId": member_id,
    }


@router.post("/rooms/join")
async def join_room(payload: JoinRoomRequest) -> dict:
    try:
        room, member_id = store.join_room(payload.invite_code, payload.display_name, payload.password)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Invite code not found") from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error

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
        reply_dict = None
        if payload.reply_to:
            reply_dict = {"id": payload.reply_to.id, "senderName": payload.reply_to.sender_name, "content": payload.reply_to.content}
        message = store.add_message(
            room_id,
            payload.sender_id,
            payload.content,
            reply_to=reply_dict,
            msg_type=payload.type or "text",
            private_to=payload.private_to,
            whisper_to=payload.whisper_to,
            mention_ids=payload.mention_ids
        )
        room = store.get_room(room_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room or member not found") from error

    # For private messages, broadcast a sanitized room to non-recipients
    # Currently we broadcast full room; the frontend filters private messages
    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)

    return {"message": message}


@router.post("/rooms/{room_id}/rolls")
async def roll_in_room(room_id: str, payload: RollDiceRequest) -> dict:
    try:
        roll = roll_dice(
            payload.expression,
            target_value=payload.target_value,
            bonus_penalty=payload.bonus_penalty,
            label=payload.label,
            hidden=payload.hidden,
        )
        roll_record = store.add_dice_roll(room_id, payload.roller_id, roll)
        room = store.get_room(room_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room or member not found") from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)

    return {"roll": roll_record}


@router.post("/rooms/{room_id}/characters/npc")
async def create_npc(room_id: str, name: str = Form("NPC"), keeper_id: str = Form(..., alias="keeperId")) -> dict:
    try:
        character = store.create_npc(room_id, keeper_id, name)
        room = store.get_room(room_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room or member not found") from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"character": character}


@router.post("/rooms/{room_id}/characters/upload")
async def upload_character(room_id: str, owner_id: str = Form(..., alias="ownerId"), file: UploadFile = File(...)) -> dict:
    try:
        content = await file.read()
        character = parse_character_card(content, file.filename or "character.xlsx")
        character_record = store.add_character(room_id, owner_id, character)
        room = store.get_room(room_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room or member not found") from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)

    return {"character": character_record}


@router.patch("/rooms/{room_id}/characters/{character_id}")
async def update_character(room_id: str, character_id: str, payload: UpdateCharacterRequest) -> dict:
    try:
        character = store.update_character(
            room_id,
            character_id,
            payload.editor_id,
            {
                "basic": payload.basic,
                "attributes": [item.model_dump() for item in payload.attributes] if payload.attributes else None,
                "keeperNotes": payload.keeper_notes,
                "lockedFields": payload.locked_fields,
                "status": payload.status,
            },
        )
        room = store.get_room(room_id)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room, member, or character not found") from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)

    return {"character": character}


# ---------- Voice messages ----------

@router.post("/rooms/{room_id}/voice")
async def upload_voice_message(
    room_id: str,
    sender_id: str = Form(..., alias="senderId"),
    duration: str = Form("0"),
    file: UploadFile = File(...),
) -> dict:
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Audio file too large (max 50 MB)")

    ext = ".webm"
    fname = file.filename or ""
    if fname.lower().endswith(".wav"):
        ext = ".wav"
    elif fname.lower().endswith(".ogg") or fname.lower().endswith(".opus"):
        ext = ".ogg"
    elif fname.lower().endswith(".mp3"):
        ext = ".mp3"

    upload_dir = settings.data_dir / "uploads" / room_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    voice_id = uuid4().hex
    voice_path = upload_dir / f"{voice_id}{ext}"
    voice_path.write_bytes(content)

    voice_record = {
        "id": voice_id,
        "roomId": room_id,
        "senderId": sender_id,
        "url": f"/api/rooms/{room_id}/voice/{voice_id}{ext}",
        "duration": float(duration) if duration else 0,
        "size": len(content),
        "createdAt": store._now(),
    }

    try:
        message = store.add_voice_message(room_id, sender_id, voice_record)
        room = store.get_room(room_id)
    except KeyError as error:
        voice_path.unlink(missing_ok=True)
        raise HTTPException(status_code=404, detail="Room or member not found") from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"voice": voice_record, "message": message}


@router.get("/rooms/{room_id}/voice/{filename:path}")
async def get_voice_file(room_id: str, filename: str):
    from fastapi.responses import FileResponse
    voice_path = settings.data_dir / "uploads" / room_id / filename
    if not voice_path.exists():
        raise HTTPException(status_code=404, detail="Voice file not found")
    media = "audio/webm"
    if filename.endswith(".wav"):
        media = "audio/wav"
    elif filename.endswith(".mp3"):
        media = "audio/mpeg"
    elif filename.endswith(".ogg"):
        media = "audio/ogg"
    return FileResponse(voice_path, media_type=media)


# ---------- Room lifecycle ----------

@router.post("/rooms/{room_id}/activate")
async def activate_room(room_id: str, editor_id: str = Form(..., alias="editorId")) -> dict:
    try:
        room = store.activate_room(room_id, editor_id)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room or member not found") from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"room": room}

# ---------- Room theme ----------

@router.post("/rooms/{room_id}/theme")
async def set_room_theme(room_id: str, theme: str = Form("black"), editor_id: str = Form(..., alias="editorId")) -> dict:
    try:
        room = store.set_room_theme(room_id, theme, editor_id)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room or member not found") from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"room": room}

# ---------- Room summary ----------

@router.post("/rooms/{room_id}/end")
async def end_room(room_id: str, editor_id: str = Form(..., alias="editorId")) -> dict:
    try:
        room = store.end_room(room_id, editor_id)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room or member not found") from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"room": room}


@router.get("/rooms/{room_id}/summary")
async def get_summary(room_id: str) -> dict:
    try:
        room = store.get_room(room_id)
        summary = room.get("summary") or store.generate_summary(room_id)
        return {"summary": summary}
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room not found") from error


@router.post("/rooms/{room_id}/summary")
async def save_summary_route(room_id: str, editor_id: str = Form(..., alias="editorId"), draft: str = Form("")) -> dict:
    try:
        summary = store.save_summary(room_id, editor_id, draft)
        room = store.get_room(room_id)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room or member not found") from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"summary": summary}


# ---------- COC 7e Advanced Rules ----------

@router.post("/rooms/{room_id}/coc/opposed")
async def opposed_roll(room_id: str, expression: str = Form("1d100"), target: str = Form("50"), opponentExpression: str = Form("1d100"), opponentTarget: str = Form("50")) -> dict:
    from app.modules.dice.roller import roll_dice as rd
    actor = rd(expression, target_value=int(target))
    opponent = rd(opponentExpression, target_value=int(opponentTarget))
    result = opposed_check(actor["total"], int(target), opponent["total"], int(opponentTarget))
    return {"actor": actor, "opponent": opponent, "result": result}

@router.post("/rooms/{room_id}/coc/heal")
async def heal_check(room_id: str, hpCurrent: str = Form("0"), hpMax: str = Form("10"), healType: str = Form("first_aid")) -> dict:
    chp, mhp = int(hpCurrent), int(hpMax)
    if healType == "medicine":
        return medicine_check(chp, mhp)
    return first_aid_check(chp, mhp)

@router.post("/rooms/{room_id}/coc/wound")
async def wound_check(room_id: str, damage: str = Form("0"), hpMax: str = Form("10")) -> dict:
    return major_wound_check(int(damage), int(hpMax))

@router.post("/rooms/{room_id}/coc/insanity")
async def insanity_roll(room_id: str, sanLoss: str = Form("0"), currentSAN: str = Form("50"), maxSAN: str = Form("50")) -> dict:
    return insanity_check(int(sanLoss), int(currentSAN), int(maxSAN))

@router.post("/rooms/{room_id}/coc/malfunction")
async def malf_check(room_id: str, total: str = Form("0"), malfValue: str = Form("96")) -> dict:
    return weapon_malfunction_check(int(total), int(malfValue))

async def room_socket(websocket: WebSocket, room_id: str, member_id: str) -> None:
    try:
        room = store.set_member_online(room_id, member_id, True)
    except KeyError:
        await websocket.close(code=4404)
        return

    await manager.connect(room_id, websocket, member_id)
    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)

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

        await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
