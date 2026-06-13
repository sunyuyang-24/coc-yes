import asyncio
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from uuid import uuid4

from app.core.config import settings
from app.modules.characters.parser import parse_character_card
from app.modules.characters.schemas import UpdateCharacterRequest
import json as _json

from app.modules.dice.roller import (
    roll_dice, opposed_check, pushing_check,
    first_aid_check, medicine_check, major_wound_check,
    insanity_check, weapon_malfunction_check,
)
from app.modules.dice.schemas import RollDiceRequest
from app.modules.rooms.schemas import (
    CreateRoomRequest, JoinRoomRequest, SendMessageRequest,
    CheckRequest, SanCheckRequest, CombatActionRequest,
    ChaseActionRequest, UpdateIntroRequest,
)
from app.modules.rooms.deps import store, manager

router = APIRouter()


def _resolve_target_from_character(character: dict, skill_name: str | None,
                                    attribute_key: str | None, difficulty: str) -> int:
    if skill_name:
        for sk in character.get("skills", []):
            if sk.get("name") == skill_name:
                val = int(sk.get("value") or 50)
                return val if difficulty == "regular" else (val // 2 if difficulty == "hard" else val // 5)
    if attribute_key:
        for attr in character.get("attributes", []):
            if attr.get("key") == attribute_key:
                val = int(attr.get("value") or 50)
                return val if difficulty == "regular" else (val // 2 if difficulty == "hard" else val // 5)
    return 50


@router.get("/rooms/mine")
async def my_rooms(request: Request) -> dict:
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"rooms": store.get_rooms_by_user(user_id)}


@router.post("/rooms/{room_id}/bind")
async def bind_member(room_id: str, request: Request) -> dict:
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    body = await request.json()
    member_id = body.get("memberId", "")
    if not member_id:
        raise HTTPException(status_code=400, detail="memberId is required")
    try:
        room = store.bind_member_to_user(room_id, member_id, user_id)
        return {"room": room}
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/rooms")
async def create_room(payload: CreateRoomRequest) -> dict:
    room, member_id = store.create_room(payload.name, payload.keeper_name, payload.password)
    room.pop("password", None)
    return {
        "room": room,
        "currentMemberId": member_id,
    }


@router.post("/rooms/join")
async def join_room(payload: JoinRoomRequest) -> dict:
    try:
        room, member_id = store.join_room(payload.invite_code, payload.display_name, payload.password, payload.role or "player")
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Invite code not found") from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error

    await manager.broadcast(room["id"], {"type": "room_update", "room": room}, store)

    room.pop("password", None)
    return {
        "room": room,
        "currentMemberId": member_id,
    }


@router.get("/rooms/{room_id}")
async def get_room(room_id: str, member_id: str = "") -> dict:
    try:
        if member_id:
            room = store.get_room_sanitized(room_id, member_id)
        else:
            room = store.get_room(room_id)
        # Never expose room password in API responses
        room.pop("password", None)
        return {"room": room}
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room not found") from error


@router.post("/rooms/{room_id}/messages")
async def send_message(room_id: str, payload: SendMessageRequest) -> dict:
    try:
        reply_dict = None
        if payload.reply_to:
            reply_dict = {"id": payload.reply_to.id, "senderName": payload.reply_to.sender_name, "content": payload.reply_to.content}
        attachments = None
        if payload.attachments:
            attachments = [
                {
                    "url": a.url,
                    "filename": a.filename,
                    "size": a.size,
                    "contentType": a.content_type,
                }
                for a in payload.attachments
            ]
        message = store.add_message(
            room_id,
            payload.sender_id,
            payload.content or "",
            reply_to=reply_dict,
            msg_type=payload.type or (attachments and "attachment") or "text",
            private_to=payload.private_to,
            whisper_to=payload.whisper_to,
            mention_ids=payload.mention_ids,
            attachments=attachments,
            as_character_id=payload.as_character_id,
        )
        room = store.get_room(room_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error

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
        roll_record = store.add_dice_roll(room_id, payload.roller_id, roll, as_character_id=payload.as_character_id)
        room = store.get_room(room_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)

    return {"roll": roll_record}


# ── 角色卡定向投骰（KP 可扮演任意角色卡，玩家仅限自己） ──
@router.post("/rooms/{room_id}/rolls/character")
async def roll_with_character(
    room_id: str,
    payload: CheckRequest,
    *,
    expression: str = "1d100",
    bonus_penalty: int = 0,
) -> dict:
    try:
        roll_record = store.character_roll(
            room_id,
            payload.editor_id or payload.character_id,
            payload.character_id,
            expression=expression or "1d100",
            skill_name=payload.skill_name,
            attribute_key=payload.attribute_key,
            difficulty=payload.difficulty or "regular",
            bonus_penalty=bonus_penalty,
            hidden=payload.hidden,
        )
        room = store.get_room(room_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"roll": roll_record}


# ── 对抗检定（KP 用 NPC / 玩家用自己角色卡） ──
@router.post("/rooms/{room_id}/coc/opposed")
async def opposed_roll(room_id: str, payload: CheckRequest) -> dict:
    try:
        room = store._require_room(room_id)
        actor = store._find_member(room, payload.editor_id or payload.character_id)
        actor_char = store._find_character(room, payload.character_id)
        actor_target = _resolve_target_from_character(
            actor_char, payload.skill_name, payload.attribute_key, payload.difficulty
        )
        actor_roll = roll_dice("1d100", target_value=actor_target, hidden=payload.hidden,
                               label=f"{actor_char.get('basic', {}).get('name', '??')} | {payload.skill_name or payload.attribute_key or '检定'}")

        opponent_character_id = getattr(payload, "opponent_character_id", None)
        opponent_roll = None
        opponent_target: int | None = None
        if opponent_character_id:
            opponent_char = store._find_character(room, opponent_character_id)
            opponent_target = _resolve_target_from_character(
                opponent_char, getattr(payload, "opponent_skill_name", None),
                getattr(payload, "opponent_attribute_key", None), "regular"
            )
            opponent_roll = roll_dice("1d100", target_value=opponent_target, hidden=payload.hidden,
                                      label=f"{opponent_char.get('basic', {}).get('name', '??')} | 对抗")
            # 记录第二颗骰子
            store.add_dice_roll(room_id, actor["id"], opponent_roll, as_character_id=opponent_character_id)

        # 主投骰（actor）——记录到聊天
        roll_record = store.add_dice_roll(room_id, actor["id"], actor_roll, as_character_id=payload.character_id)
        room_snapshot = store.get_room(room_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room_snapshot}, store)
    return {
        "actorRoll": roll_record,
        "opponentRoll": opponent_roll,
    }


@router.post("/rooms/{room_id}/characters/npc")
async def create_npc(room_id: str, name: str = Form("NPC"), keeper_id: str = Form(..., alias="keeperId")) -> dict:
    try:
        character = store.create_npc(room_id, keeper_id, name)
        room = store.get_room(room_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room or member not found") from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"character": character}


@router.post("/rooms/{room_id}/characters/npc/text")
async def create_npc_from_text(room_id: str, keeper_id: str = Form(..., alias="keeperId"), npc_text: str = Form("", alias="npcText")) -> dict:
    try:
        character = store.create_npc_from_text(room_id, keeper_id, npc_text)
        room = store.get_room(room_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room or member not found") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

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
    # Check size before reading the entire file into memory
    max_size = 50 * 1024 * 1024  # 50 MB
    if file.size is not None and file.size > max_size:
        raise HTTPException(status_code=400, detail="Audio file too large (max 50 MB)")
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(content) > max_size:
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
    if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
        raise HTTPException(status_code=400, detail="Invalid filename")
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


# ---------- Message deletion ----------

@router.post("/rooms/{room_id}/messages/{message_id}/delete")
async def delete_message(room_id: str, message_id: str, editor_id: str = Form(..., alias="editorId")) -> dict:
    try:
        store.delete_message(room_id, message_id, editor_id)
        room = store.get_room(room_id)
    except KeyError as error:
        detail = str(error)
        if detail == "message_not_found":
            raise HTTPException(status_code=404, detail="Message not found")
        raise HTTPException(status_code=404, detail="Room or member not found")
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"deleted": True}


# ---------- File / image upload ----------

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf", ".txt", ".md", ".json", ".csv"}
ALLOWED_MIMETYPES = {
    "image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml",
    "application/pdf", "text/plain", "text/markdown", "application/json", "text/csv",
}

@router.post("/rooms/{room_id}/files")
async def upload_file(
    room_id: str,
    sender_id: str = Form("", alias="senderId"),
    files: list[UploadFile] = File(...),
) -> list[dict]:
    max_size = 10 * 1024 * 1024  # 10 MB per file
    upload_dir = settings.data_dir / "uploads" / room_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for file in files:
        content = await file.read()
        if len(content) == 0:
            continue
        if len(content) > max_size:
            raise HTTPException(status_code=400, detail=f"File too large (max 10 MB): {file.filename or ''}")

        fname = file.filename or "file"
        ext = ""
        if "." in fname:
            ext = "." + fname.rsplit(".", 1)[1].lower()
        file_id = uuid4().hex
        out_path = upload_dir / f"{file_id}{ext}"
        out_path.write_bytes(content)

        url = f"/api/rooms/{room_id}/files/{file_id}{ext}"
        results.append({
            "id": file_id,
            "url": url,
            "filename": fname,
            "size": len(content),
            "contentType": file.content_type or "application/octet-stream",
        })

    return results


@router.get("/rooms/{room_id}/files/{filename:path}")
async def get_file(room_id: str, filename: str):
    if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    from fastapi.responses import FileResponse
    file_path = settings.data_dir / "uploads" / room_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mime_map = {
        "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "gif": "image/gif", "webp": "image/webp", "svg": "image/svg+xml",
        "pdf": "application/pdf", "txt": "text/plain", "md": "text/markdown",
        "json": "application/json", "csv": "text/csv",
    }
    return FileResponse(file_path, media_type=mime_map.get(ext, "application/octet-stream"))


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


@router.post("/rooms/{room_id}/delete")
async def delete_room(room_id: str, editor_id: str = Form(..., alias="editorId")) -> dict:
    try:
        room = store.get_room(room_id)
        editor = next((m for m in room.get("members", []) if m["id"] == editor_id), None)
        if not editor or editor["role"] != "keeper":
            raise HTTPException(status_code=403, detail="Only keeper can delete the room")
        store.delete_room(room_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Room not found") from None
    return {"deleted": True}


@router.post("/rooms/{room_id}/characters/remove")
async def remove_room_character(room_id: str, member_id: str = Form(..., alias="memberId")) -> dict:
    try:
        room = store.remove_character(room_id, member_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Room or member not found") from None
    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"removed": True}


@router.post("/rooms/{room_id}/characters/{character_id}/delete")
async def delete_character(room_id: str, character_id: str, editor_id: str = Form(..., alias="editorId")) -> dict:
    try:
        room = store.delete_character(room_id, character_id, editor_id)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except KeyError as error:
        detail = str(error)
        if detail == "character_not_found":
            raise HTTPException(status_code=404, detail="Character not found")
        raise HTTPException(status_code=404, detail="Room or member not found")

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"deleted": True}


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


# ---------- Module Intro ----------

@router.patch("/rooms/{room_id}/intro")
async def update_intro(room_id: str, payload: UpdateIntroRequest) -> dict:
    try:
        room = store.update_module_intro(room_id, payload.editor_id, payload.intro)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Room or member not found") from error

    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
    return {"room": room}


async def room_socket(websocket: WebSocket, room_id: str, member_id: str) -> None:
    try:
        room = store.set_member_online(room_id, member_id, True)
    except KeyError:
        await websocket.close(code=4404)
        return

    await manager.connect(room_id, websocket, member_id)
    await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)

    # 心跳任务：每30秒发送ping，防止代理/防火墙断开空闲连接
    async def heartbeat():
        while True:
            await asyncio.sleep(30)
            try:
                await websocket.send_json({"type": "ping"})
            except Exception:
                break

    heartbeat_task = asyncio.create_task(heartbeat())

    try:
        sanitized = store.get_room_sanitized(room_id, member_id)
        await websocket.send_json({"type": "room_state", "room": sanitized})

        while True:
            raw = await websocket.receive_text()
            payload = _json.loads(raw)
            msg_type = payload.get("type", "")

            # WebRTC signaling relay
            if msg_type in ("webrtc_offer", "webrtc_answer", "webrtc_ice", "webrtc_mute", "webrtc_unmute", "webrtc_voice_join", "webrtc_voice_leave", "webrtc_force_mute", "webrtc_kick"):
                # KP-only commands: force_mute and kick require keeper role
                if msg_type in ("webrtc_force_mute", "webrtc_kick"):
                    sender = next((m for m in room.get("members", []) if m["id"] == member_id), None)
                    if not sender or sender["role"] != "keeper":
                        continue  # silently drop unauthorized commands

                target = payload.get("target")
                if target:
                    # Point-to-point signaling (including force_mute / kick)
                    await manager.send_to(room_id, target, {
                        "type": msg_type,
                        "from": member_id,
                        "sdp": payload.get("sdp"),
                        "candidate": payload.get("candidate"),
                        "label": payload.get("label"),
                        "muted": payload.get("muted"),
                    })
                else:
                    # Broadcast voice status to room
                    await manager.broadcast(room_id, {
                        "type": msg_type,
                        "from": member_id,
                        "muted": payload.get("muted"),
                    }, store)
    except (WebSocketDisconnect, RuntimeError, _json.JSONDecodeError):
        pass
    finally:
        heartbeat_task.cancel()
        manager.disconnect(room_id, websocket)

        try:
            room = store.set_member_online(room_id, member_id, False)
        except KeyError:
            return

        await manager.broadcast(room_id, {"type": "room_update", "room": room}, store)
        # Notify voice leave
        await manager.broadcast(room_id, {"type": "webrtc_voice_leave", "from": member_id}, store)
