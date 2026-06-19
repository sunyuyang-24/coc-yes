"""User-scoped character card management endpoints."""

from fastapi import APIRouter, HTTPException, Request

from app.modules.characters.user_chars import (
    delete_user_character,
    get_user_character,
    get_user_characters,
)

router = APIRouter()


@router.get("/user/characters")
async def list_my_characters(request: Request) -> list[dict]:
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return get_user_characters(user_id)


@router.get("/user/characters/{char_id}")
async def get_my_character(char_id: str, request: Request) -> dict:
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    char = get_user_character(user_id, char_id)
    if char is None:
        raise HTTPException(status_code=404, detail="Character not found")
    return char


@router.delete("/user/characters/{char_id}")
async def delete_my_character(char_id: str, request: Request) -> dict:
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    deleted = delete_user_character(user_id, char_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Character not found")
    return {"deleted": True}
