from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from app.core.auth_middleware import require_admin
from app.core.db import get_db
from app.modules.characters.user_chars import (
    get_user_character,
    get_user_characters,
)
from app.modules.rooms.deps import store

router = APIRouter()


@router.get("/admin/users")
async def list_users(request: Request):
    require_admin(request)
    db = get_db()
    rows = db.execute(
        """SELECT u.id, u.username, u.display_name, u.created_at, u.is_admin,
                  COUNT(DISTINCT rm.id) AS room_count,
                  COUNT(DISTINCT uc.id) AS character_count
           FROM users u
           LEFT JOIN room_members rm ON rm.user_id = u.id
           LEFT JOIN user_characters uc ON uc.user_id = u.id
           GROUP BY u.id
           ORDER BY u.created_at DESC"""
    ).fetchall()
    return [
        {
            "id": r["id"],
            "username": r["username"],
            "display_name": r["display_name"],
            "created_at": r["created_at"],
            "is_admin": bool(r["is_admin"]),
            "room_count": r["room_count"],
            "character_count": r["character_count"],
        }
        for r in rows
    ]


@router.get("/admin/users/{user_id}/rooms")
async def list_user_rooms(user_id: str, request: Request):
    require_admin(request)
    db = get_db()
    rows = db.execute(
        """SELECT rm.room_id, rm.display_name AS member_name, rm.role, rm.joined_at,
                  r.name AS room_name, r.status, r.invite_code, r.created_at, r.ended_at
           FROM room_members rm
           JOIN rooms r ON r.id = rm.room_id
           WHERE rm.user_id = ?
           ORDER BY rm.joined_at DESC""",
        (user_id,),
    ).fetchall()
    return [
        {
            "room_id": r["room_id"],
            "room_name": r["room_name"],
            "status": r["status"],
            "invite_code": r["invite_code"],
            "role": r["role"],
            "member_name": r["member_name"],
            "joined_at": r["joined_at"],
            "created_at": r["created_at"],
            "ended_at": r["ended_at"],
        }
        for r in rows
    ]


@router.get("/admin/users/{user_id}/characters")
async def list_user_characters(user_id: str, request: Request):
    require_admin(request)
    return get_user_characters(user_id)


@router.get("/admin/users/{user_id}/characters/{char_id}")
async def get_user_character_detail(user_id: str, char_id: str, request: Request):
    require_admin(request)
    char = get_user_character(user_id, char_id)
    if char is None:
        return JSONResponse({"error": "Character not found"}, status_code=404)
    return char


@router.post("/admin/users/{user_id}/rooms/{room_id}/leave")
async def admin_leave_room(user_id: str, room_id: str, request: Request):
    require_admin(request)
    try:
        removed = store.leave_room(room_id, user_id)
    except KeyError:
        return JSONResponse({"error": "Room not found"}, status_code=404)
    return {"left": removed}
